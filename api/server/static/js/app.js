(() => {
  "use strict";

  const form = document.getElementById("jack-form");
  const input = document.getElementById("jack-input");
  const submitBtn = document.getElementById("jack-submit");
  const meter = document.getElementById("meter");
  const meterLabel = document.getElementById("meter-label");
  const results = document.getElementById("results");

  const isLink = (value) => /^https?:\/\//i.test(value.trim());

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const setMeterState = (state, label) => {
    meter.dataset.state = state;
    meterLabel.textContent = label;
  };

  const clearResults = () => {
    results.innerHTML = "";
  };

  const showEmpty = (message) => {
    clearResults();
    const wrap = el("div", "empty-state");
    wrap.appendChild(el("div", "empty-state__reel"));
    wrap.appendChild(el("p", "empty-state__text", message));
    results.appendChild(wrap);
  };

  const showStatusMessage = (message, isError) => {
    clearResults();
    results.appendChild(
      el("div", `status-message${isError ? " status-message--error" : ""}`, message)
    );
  };

  // -------------------------------------------------------------
  // API calls
  // -------------------------------------------------------------
  async function apiPost(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.message || `Request failed (${res.status})`);
    }
    return data;
  }

  async function apiGet(path) {
    const res = await fetch(path);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.message || `Request failed (${res.status})`);
    }
    return data;
  }

  // -------------------------------------------------------------
  // Card builders
  // -------------------------------------------------------------

  // Builds a "RESOLUTIONS" toggle button + collapsible panel for a given
  // videoInfo. Shared by the plain video-search card and the single-result
  // card, so both offer the exact same video-download behavior.
  function buildResolutionsToggle(videoInfo) {
    const action = el("button", "card__action", "RESOLUTIONS");
    action.type = "button";

    const resolutionPanel = el("div", "resolutions");
    resolutionPanel.style.display = "none";
    resolutionPanel.style.flexDirection = "column";
    resolutionPanel.style.gap = "6px";
    resolutionPanel.style.marginTop = "8px";

    action.addEventListener("click", async () => {
      if (resolutionPanel.style.display === "flex") {
        resolutionPanel.style.display = "none";
        return;
      }

      action.disabled = true;
      action.textContent = "…";
      try {
        const resolutions = await apiPost("/download/video/resolutions", videoInfo);
        resolutionPanel.innerHTML = "";

        Object.entries(resolutions).forEach(([label, resolution]) => {
          const row = el("div", "card");
          row.style.padding = "8px 10px";

          const info = el(
            "div",
            "card__subtitle",
            `${label}${resolution.filesize_mb ? ` · ${resolution.filesize_mb} MB` : ""}`
          );
          row.appendChild(info);

          const downloadBtn = el("button", "card__action", "GET");
          downloadBtn.type = "button";
          downloadBtn.addEventListener("click", async () => {
            downloadBtn.disabled = true;
            downloadBtn.textContent = "…";
            try {
              await apiPost("/download/video", {
                ...videoInfo,
                resolution,
              });
              downloadBtn.textContent = "DONE";
            } catch (err) {
              downloadBtn.textContent = "RETRY";
              downloadBtn.disabled = false;
              console.error(err);
            }
          });
          row.appendChild(downloadBtn);

          resolutionPanel.appendChild(row);
        });

        resolutionPanel.style.display = "flex";
      } catch (err) {
        console.error(err);
      } finally {
        action.disabled = false;
        action.textContent = "RESOLUTIONS";
      }
    });

    return { action, resolutionPanel };
  }

  function buildSongCard(metadata, videoInfo) {
    const card = el("div", metadata.is_fallback ? "card card--fallback" : "card");

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "card__checkbox";
    checkbox.checked = true;
    checkbox.setAttribute("aria-label", `Include ${metadata.title || videoInfo.title}`);
    card.appendChild(checkbox);

    const cover = document.createElement("img");
    cover.className = "card__cover";
    cover.alt = "";
    cover.src = metadata.cover || "";
    cover.onerror = () => cover.remove();
    card.appendChild(cover);

    const body = el("div", "card__body");
    body.appendChild(el("div", "card__title", metadata.title || videoInfo.title));
    body.appendChild(el("div", "card__subtitle", metadata.artist || videoInfo.uploader));
    card.appendChild(body);

    if (metadata.is_fallback) {
      const badge = el("span", "card__badge card__badge--fallback", "NO MATCH");
      badge.title = "No metadata provider match — using YouTube title/uploader as-is";
      card.appendChild(badge);
    }

    card.appendChild(el("span", "card__badge", "MP3"));

    const action = el("button", "card__action", "DOWNLOAD");
    action.type = "button";

    // Shared by the button's own click handler and the playlist "DOWNLOAD ALL"
    // action, so both paths show consistent DONE/RETRY state on the card.
    let done = false;
    const download = async () => {
      if (done) return true;
      action.disabled = true;
      action.textContent = "…";
      try {
        await apiPost("/download/single", {
          title: metadata.title,
          artist: metadata.artist,
          link: metadata.link,
          artist_id: metadata.artist_id,
          cover: metadata.cover,
          tracknumber: metadata.tracknumber,
          album: metadata.album,
          lyrics: metadata.lyrics,
          release_date: metadata.release_date,
          id: videoInfo.id,
          uploader: videoInfo.uploader,
          audio_ext: videoInfo.audio_ext,
          filesize: videoInfo.filesize,
        });
        action.textContent = "DONE";
        done = true;
        return true;
      } catch (err) {
        action.textContent = "RETRY";
        action.disabled = false;
        console.error(err);
        return false;
      }
    };

    action.addEventListener("click", () => {
      download();
    });
    card.appendChild(action);

    card.appendChild(el("span", "card__badge", "MP4"));

    const { action: mp4Action, resolutionPanel } = buildResolutionsToggle(videoInfo);
    card.appendChild(mp4Action);

    const wrap = el("div");
    wrap.appendChild(card);
    wrap.appendChild(resolutionPanel);

    return { card, wrap, checkbox, download };
  }

  // Single-result card: the metadata (audio) match plus a video-resolution
  // picker for the same video, so the user can choose either format.
  function buildSingleResultCard(metadata, videoInfo) {
    const card = el("div", "card");

    const cover = document.createElement("img");
    cover.className = "card__cover";
    cover.alt = "";
    cover.src = metadata.cover || "";
    cover.onerror = () => cover.remove();
    card.appendChild(cover);

    const body = el("div", "card__body");
    body.appendChild(el("div", "card__title", metadata.title || videoInfo.title));
    body.appendChild(el("div", "card__subtitle", metadata.artist || videoInfo.uploader));
    card.appendChild(body);

    card.appendChild(el("span", "card__badge", "MP3"));

    const mp3Action = el("button", "card__action", "DOWNLOAD");
    mp3Action.type = "button";
    mp3Action.addEventListener("click", async () => {
      mp3Action.disabled = true;
      mp3Action.textContent = "…";
      try {
        await apiPost("/download/single", {
          title: metadata.title,
          artist: metadata.artist,
          link: metadata.link,
          artist_id: metadata.artist_id,
          cover: metadata.cover,
          tracknumber: metadata.tracknumber,
          album: metadata.album,
          lyrics: metadata.lyrics,
          release_date: metadata.release_date,
          id: videoInfo.id,
          uploader: videoInfo.uploader,
          audio_ext: videoInfo.audio_ext,
          filesize: videoInfo.filesize,
        });
        mp3Action.textContent = "DONE";
      } catch (err) {
        mp3Action.textContent = "RETRY";
        mp3Action.disabled = false;
        console.error(err);
      }
    });
    card.appendChild(mp3Action);

    card.appendChild(el("span", "card__badge", "MP4"));

    const { action: mp4Action, resolutionPanel } = buildResolutionsToggle(videoInfo);
    card.appendChild(mp4Action);

    const wrap = el("div");
    wrap.appendChild(card);
    wrap.appendChild(resolutionPanel);
    return wrap;
  }

  function buildUnavailableCard(entry) {
    const card = el("div", "card card--unavailable");

    const body = el("div", "card__body");
    body.appendChild(
      el("div", "card__title", entry.title || entry.id || "Unknown video")
    );
    body.appendChild(el("div", "card__subtitle", entry.reason || "unavailable"));
    card.appendChild(body);

    const badge = el("span", "card__badge card__badge--unavailable", "UNAVAILABLE");
    badge.title = entry.reason || "yt-dlp couldn't retrieve this video";
    card.appendChild(badge);

    return card;
  }

  function buildVideoCard(videoInfo) {
    const card = el("div", "card");

    const body = el("div", "card__body");
    body.appendChild(el("div", "card__title", videoInfo.title));
    body.appendChild(el("div", "card__subtitle", videoInfo.uploader));
    card.appendChild(body);

    card.appendChild(el("span", "card__badge", "MP4"));

    const { action, resolutionPanel } = buildResolutionsToggle(videoInfo);
    card.appendChild(action);

    const wrap = el("div");
    wrap.appendChild(card);
    wrap.appendChild(resolutionPanel);
    return wrap;
  }

  // -------------------------------------------------------------
  // Response renderers
  // -------------------------------------------------------------
  function renderSingle(resource) {
    clearResults();
    results.appendChild(buildSingleResultCard(resource.metadata, resource.video_info));
  }

  // Runs `worker` over `items` with at most `limit` running concurrently.
  async function runWithConcurrency(items, limit, worker) {
    let cursor = 0;
    const runners = new Array(Math.min(limit, items.length)).fill(null).map(
      async () => {
        while (cursor < items.length) {
          const index = cursor++;
          await worker(items[index], index);
        }
      }
    );
    await Promise.all(runners);
  }

  function renderPlaylist(resource) {
    clearResults();
    const info = resource.playlist_info;

    const header = el("div", "playlist-header");
    const cover = document.createElement("img");
    cover.className = "playlist-header__cover";
    cover.alt = "";
    cover.src = info.cover || "";
    cover.onerror = () => cover.remove();
    header.appendChild(cover);

    const headerBody = el("div");
    headerBody.appendChild(el("div", "playlist-header__title", info.name));
    const fallbackCount = info.provider_metadata.filter((m) => m && m.is_fallback).length;
    const unavailableList = info.unavailable || [];
    const countParts = [`${info.youtube_metadata.length} TRACKS`];
    if (fallbackCount) countParts.push(`${fallbackCount} NO MATCH`);
    if (unavailableList.length) countParts.push(`${unavailableList.length} UNAVAILABLE`);
    headerBody.appendChild(el("div", "playlist-header__count", countParts.join(" · ")));
    header.appendChild(headerBody);
    results.appendChild(header);

    // Build song cards first so the "select all" / "download all" controls
    // can operate on the actual checkbox + download refs.
    const songRefs = info.provider_metadata
      .map((metadata, i) => ({ metadata, videoInfo: info.youtube_metadata[i] }))
      .filter((entry) => entry.videoInfo)
      .map((entry) => buildSongCard(entry.metadata, entry.videoInfo));

    if (songRefs.length) {
      const actions = el("div", "playlist-actions");

      const selectAllLabel = el("label", "playlist-actions__select-all");
      const selectAll = document.createElement("input");
      selectAll.type = "checkbox";
      selectAll.checked = true;
      selectAllLabel.appendChild(selectAll);
      selectAllLabel.appendChild(document.createTextNode("SELECT ALL"));
      actions.appendChild(selectAllLabel);

      selectAll.addEventListener("change", () => {
        songRefs.forEach((ref) => {
          ref.checkbox.checked = selectAll.checked;
        });
      });

      // If someone unchecks/checks an individual track, keep "select all" in sync.
      songRefs.forEach((ref) => {
        ref.checkbox.addEventListener("change", () => {
          selectAll.checked = songRefs.every((r) => r.checkbox.checked);
        });
      });

      const downloadAllBtn = el("button", "card__action playlist-actions__download-all", "DOWNLOAD ALL");
      downloadAllBtn.type = "button";
      downloadAllBtn.addEventListener("click", async () => {
        const selected = songRefs.filter((ref) => ref.checkbox.checked);
        if (!selected.length) return;

        downloadAllBtn.disabled = true;
        let completed = 0;
        let failed = 0;
        downloadAllBtn.textContent = `DOWNLOADING 0/${selected.length}`;

        await runWithConcurrency(selected, 3, async (ref) => {
          const ok = await ref.download();
          if (ok) completed++;
          else failed++;
          downloadAllBtn.textContent = `DOWNLOADING ${completed + failed}/${selected.length}`;
        });

        downloadAllBtn.textContent = failed
          ? `DONE · ${failed} FAILED`
          : "DONE";
        downloadAllBtn.disabled = false;
      });
      actions.appendChild(downloadAllBtn);

      results.appendChild(actions);
    }

    songRefs.forEach((ref) => results.appendChild(ref.wrap));

    unavailableList.forEach((entry) => {
      results.appendChild(buildUnavailableCard(entry));
    });
  }

  function renderSearch(response) {
    clearResults();
    if (!response.results || response.results.length === 0) {
      showEmpty("NO RESULTS — try a different search");
      return;
    }
    response.results.forEach((videoInfo) => {
      results.appendChild(buildVideoCard(videoInfo));
    });
  }

  // -------------------------------------------------------------
  // Submit handler
  // -------------------------------------------------------------
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const value = input.value.trim();
    if (!value) return;

    submitBtn.disabled = true;
    setMeterState("loading", "PULLING…");

    try {
      if (isLink(value)) {
        const resource = await apiPost("/media/resolve", { url: value });
        if (resource.resource_type === "single") {
          renderSingle(resource);
        } else {
          renderPlaylist(resource);
        }
      } else {
        const response = await apiGet(`/media/search?q=${encodeURIComponent(value)}`);
        renderSearch(response);
      }
      setMeterState("success", "LOCKED");
    } catch (err) {
      console.error(err);
      showStatusMessage(err.message || "Something went wrong", true);
      setMeterState("error", "NO SIGNAL");
    } finally {
      submitBtn.disabled = false;
    }
  });
})();
