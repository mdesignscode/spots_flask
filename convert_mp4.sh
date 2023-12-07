#!/bin/bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <input_directory>"
    exit 1
fi

input_dir="$1"
output_dir="$input_dir"

# Check if the input directory exists
if [ ! -d "$input_dir" ]; then
    echo "Error: Input directory does not exist."
    exit 1
fi

# Loop through all MP4 files in the input directory
for input_file in "$input_dir"/*.mp4; do
    # Extract the file name without extension
    filename=$(basename -- "$input_file")
    filename_noext="${filename%.*}"

    # Create the output file path
    output_file="$output_dir/$filename_noext.mp3"

    # Convert MP4 to MP3 using FFmpeg
    ffmpeg -i "$input_file" -vn -acodec libmp3lame -q:a 4 "$output_file"

    echo "Converted: $filename to $output_file"
done

echo "Conversion complete!"
