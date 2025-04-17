# Simple Photoeditor

Simple Photoeditor is an open-source Python-based multi platform image editing tool inspired by the classic Microsoft Photoeditor. While the original software is no longer supported and has several limitations, it offered a user-friendly and minimalistic interface for document scanning and processing. Simple Photoeditor aims to recreate that experience with modern functionality, allowing users to create, edit, and process images efficiently.

## Features

- **Image Creation and Editing**: Create new images or edit existing ones with a simple, intuitive interface.
- **Multi-Image Composition**: Combine multiple images onto a single canvas for composite designs.
- **Standard Operations**:
  - Resize, crop, and rotate images.
  - Adjust brightness, contrast, and other basic properties.
- **Scanning and Printing**: Scan documents directly into the editor and print images with ease.
- **Minimalistic Design**: Streamlined interface for quick and efficient workflows.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/simple-photoeditor.git
   cd simple-photoeditor
   ```

2. **Set Up a Virtual Environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Key Dependencies

- **OpenCV-Python-Headless** (`opencv-python-headless==4.11.0.86`): For image processing and manipulation.
- **Pillow** (`pillow==11.1.0`): For advanced image handling and editing.
- **PyQt5** (`PyQt5==5.15.11`): For the graphical user interface.
- **NumPy** (`numpy==2.2.3`): For efficient array operations.
- **PyInstaller** (`pyinstaller==6.12.0`): For packaging the application into an executable.

For a full list of dependencies, see `requirements.txt`.


## Download

Last Relese [v1.0] (https://github.com/li-zard/Simple-Photoeditor/releases/tag/%23)
    - Windows: (https://github.com/li-zard/Simple-Photoeditor/releases/download/%23/SimplePhotoEditor_v1.0.exe)
## Usage

1. Run the application:
   ```bash
   python main.py
   ```

2. Use the interface to:
   - Open or scan images.
   - Perform edits (resize, crop, rotate, etc.).
   - Combine multiple images on a canvas.
   - Save or print your work.

## Contributing

We welcome contributions! To get started:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Commit your changes (`git commit -m "Add your feature"`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a Pull Request.


## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by the simplicity and functionality of Microsoft Photoeditor.
- Built with the power of Python and open-source libraries.