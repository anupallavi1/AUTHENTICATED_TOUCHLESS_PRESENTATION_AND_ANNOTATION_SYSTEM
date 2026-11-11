# Authenticated Touchless Presentation and Annotation System

An intelligent presentation system that allows users to control PowerPoint presentations without physically touching a keyboard or mouse. It combines hand gesture recognition, voice commands, user authentication, digital annotation and AI-powered presentation summarization.

## Features

- **User Authentication:** Login and face verification for authorized access.
- **Hand Gesture Recognition:** Control presentation slides using hand gestures.
- **Voice Control:** Navigate presentations using voice commands.
- **Digital Annotation:** Draw and annotate directly on the screen using hand gestures.
- **Speaker Verification:** Verify the presenter's voice before accepting voice commands.
- **AI-Powered Summarization:** Generate summaries of uploaded PowerPoint presentations.
- **PowerPoint Handling:** Upload and process presentation files.

## Technologies Used

| Category | Technologies |
|---|---|
| Programming Language | Python |
| Backend | Flask |
| Frontend | HTML, CSS |
| Database | MySQL |
| Computer Vision | OpenCV, MediaPipe |
| Hand Tracking | MediaPipe Hand Landmarker |
| Face Verification | Face Recognition |
| Voice Recognition | SpeechRecognition, PyAudio |
| Speaker Verification | SpeechBrain |
| AI Summarization | Google Gemini |
| PowerPoint Processing | Python-PPTX |

## Project Structure

```text
AUTHENTICATED_TOUCHLESS_PRESENTATION_AND_ANNOTATION_SYSTEM/
│
├── templates/
│   ├── home.html
│   ├── login.html
│   ├── file_summarizer.html
│   ├── upload_file.html
│   └── upload_file_voice.html
│
├── main.py
├── DBConnection.py
├── face_verification.py
├── gesture_controller_app.py
├── air_drawing.py
├── voice_control.py
├── speaker_verification.py
├── ppt_splitter.py
├── ppt_summarizer.py
│
├── gestures.txt
├── hand_landmarker.task
├── requirements.txt
├── .env.example
└── .gitignore
```

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/anupallavi1/AUTHENTICATED_TOUCHLESS_PRESENTATION_AND_ANNOTATION_SYSTEM.git
```

Navigate to the project folder:

```bash
cd AUTHENTICATED_TOUCHLESS_PRESENTATION_AND_ANNOTATION_SYSTEM
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Python 3.10 is specified in the project requirements.

### 4. Configure Environment Variables

Create a `.env` file in the project root directory using `.env.example` as a reference.

Add your own MySQL username and password:

```env
DB_USER=your_mysql_username
DB_PASSWORD=your_mysql_password
```

Do not upload your actual `.env` file or passwords to GitHub.

### 5. Database Configuration

- Install and start MySQL.
- Create a database named `gesture_present`.
- Configure the database credentials in the `.env` file.
- Ensure the required database tables are available.

### 6. Additional Requirements

The project also requires:

- Microsoft PowerPoint for PowerPoint splitting functionality.
- Tesseract OCR for text recognition.
- FFmpeg for audio processing.
- A webcam and microphone for gesture and voice-based interaction.

The speaker verification model is downloaded when first required.

## Running the Application

After completing the installation and configuration, run:

```bash
python main.py
```

Open the local Flask application in your web browser using the address displayed in the terminal.

## How to Use

1. Open the application in your browser.
2. Log in and complete the required authentication.
3. Access the presentation control features.
4. Upload a PowerPoint presentation.
5. Use hand gestures or voice commands to control slides.
6. Use digital annotation to draw on the presentation.
7. Generate AI-powered summaries of presentation content.

## Future Enhancements

- Improved gesture recognition accuracy.
- Support for additional presentation formats.
- Enhanced authentication and security.
- Improved real-time voice interaction.

## Author

**Anupallavi K V**

B.Tech Computer Science and Engineering

---

*This project demonstrates the integration of computer vision, voice recognition, authentication and artificial intelligence to create a touchless presentation experience.*
