---
sidebar_position: 1
---

# Radio-Spectrum SHARC

## Introduction to SHARC

Welcome to **SHARC**, a powerful simulator designed to support **SHARing and Compatibility** studies of radiocommunication systems, focusing on **modeling and simulating IMT networks and systems** for use in sharing and compatibility studies.

### Purpose of SHARC

SHARC helps users simulate and evaluate various radiocommunication systems to understand how they share and coexist in the radio spectrum. Whether you're assessing interference, spectrum allocation, or compatibility across different communication technologies, SHARC provides the tools you need to ensure the optimal use of radio frequencies.

## 📚 Key Features of SHARC

- **Compatibility Studies**: Simulate interactions between different systems like IMT (International Mobile Telecommunications), satellite services, and terrestrial systems.
- **Flexible and Scalable**: SHARC supports simulation of both **satellite** and **terrestrial** communication systems, offering both large-scale global studies and localized scenarios.
- **Modular Architecture**: The software is designed to be easily extensible, allowing users to add their own models, systems, and study areas.
- **Integration with ITU Framework**: SHARC operates according to the international guidelines set by the ITU-R recommendations, ensuring that simulations align with industry standards.

---

## ⚙️ Requirements 
Before getting started, make sure you have:

- ✅ **Python 3.12 or newer**  
  Download from the [official Python website](https://www.python.org/downloads/)
- ✅ **virtualenv** module installed  
  Install with `pip install virtualenv` if not already installed
- ✅ **Git** (for cloning the repository) **(optional)**  
  Download from the [official Git website](https://git-scm.com/downloads)

> ℹ️ SHARC follows the [PEP 8 Style Guide](https://peps.python.org/pep-0008/) for Python code style and formatting.

---

## 🦈 Get Started with SHARC

Ready to dive into SHARC? Follow the steps below to set up SHARC.

### 📦 Installing SHARC package

#### 🤖 Automatic Installer (Recommended)

1. Ensure [Python 3.12](https://www.python.org/downloads/) or newer is installed.
2. [Download the SHARC .zip package](https://github.com/Radio-Spectrum/SHARC/archive/refs/heads/development.zip)
3. Extract the archive.
4. Run the installation script:
  - Continue the installation process by clicking two times in

    `install.py`

  or

  - In command terminal execute:
     
   ```bash
   python3 install.py
   ```
   
This script will:

- Create and activate a virtual environment  
- Install all required dependencies  
- Set up SHARC for development or use

---

#### 💻 Manual Installation

Prefer doing it step-by-step? Here's how:

1. Clone the SHARC repository:
   ```bash
   git clone https://github.com/Radio-Spectrum/SHARC
   cd SHARC/
   ```
2. Ensure Python 3.12 and `virtualenv` are installed.
3. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Install SHARC in editable mode:
   ```bash
   pip install -e .
   ```

---

## Contributing
We welcome all contributions — whether you're fixing a bug, implementing a new feature, or improving the documentation.

Please check out our [CONTRIBUTING](https://projectsharc.vercel.app/docs/Contributing) for detailed guidelines on how to contribute, branch naming, testing, and submitting pull requests.
