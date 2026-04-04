# 🎧 Spots

Spots is a modular music coordination library that unifies multiple providers (e.g. Deezer, Spotify, YouTube) into a single, consistent interface.

It resolves tracks across platforms, matches metadata intelligently, and enables downloading, playlist handling, and media conversion — all through a clean, configurable API.

---

## ✨ Features

- 🔍 **Multi-provider search**
  - Supports multiple metadata providers with fallback resolution

- 🧠 **Intelligent track matching**
  - Matches tracks across platforms using pattern-based scoring

- 🎵 **Unified media resolution**
  - Seamlessly map metadata → YouTube → downloadable media

- ⚡ **Provider fallback system**
  - Automatically falls back when a provider fails

- 🗂️ **Built-in caching**
  - Reduces redundant API calls and speeds up repeated queries

- ⚙️ **Config-driven architecture**
  - Enable/disable integrations (Spotify, YouTube, etc.)

- 📦 **Download + conversion pipeline**
  - Handles media extraction and conversion (via yt-dlp)

---

## 📦 Installation

```bash
pip install spots
```

---

## ⚙️ Setup

### Run the setup script:

```bash
spots setup
```

* follow the prompts to generate the config folder


---

## 🚀 Usage
```bash
# search a title
# required search format: `Artist - Title`
spots download "Kelsey Lynn - Modern Day Marilyn Monroe"

# download a direct url
spots download "https://www.youtube.com/watch?v=UmZPa5Qudtw"
```

Spots will:

* Resolve the track via metadata providers
* Match it to a YouTube video
* Download and convert it
* Store results locally

---

## 🎮 Available commands

* download - downloads a direct url or a search query
  ```bash
  spots download "Kelsey Lynn - Modern Day Marilyn Monroe"
  ```
* migrate-likes - transfers likes from Spotify to YouTube (more providers coming soon...)
  ```bash
  spots migrate-likes
  ```
* add-to-history - adds a user's downloaded songs to the Spots history. Avoids duplicate downloads.
  ```bash
  spots add-to-history path-to-music
  ```
* remove-duplicates - removes duplicate songs in a given folder.
  ```bash
  spots remove-duplicates path-to-music
  ```

---

## ⚠️ Important

    The Spotify API content may not be downloaded using this project. This project is created for personal use only and is intended for educational purposes. Any use of this project to download or distribute copyrighted material without proper authorization is against the terms of service of Spotify and other involved platforms. The project's author and contributors are not responsible for any misuse of this software.

## 🤝 Contributing

Contributions are welcome.

If you're adding a provider or improving matching logic, open a PR with a clear description of changes.

---

## 📄 License

GPL-3.0-or-later

---

## 💬 Summary

Spots is designed to make cross-platform music workflows simple:

Give it a track — it figures out the rest.
