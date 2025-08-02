# Place test images here

This directory is mounted as a read-only volume in the Docker containers.
You can place test images here and reference them in your API calls.

Example usage in API:
- Place image as `./images/test.jpg`
- In Docker container, access as `/app/images/test.jpg`

Supported formats:
- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- BMP (.bmp)
- TIFF (.tiff, .tif)

Note: This directory is ignored in the Docker build context (.dockerignore) to reduce build size.
