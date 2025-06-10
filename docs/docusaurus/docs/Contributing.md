# Contributing to SHARC

Contributions are welcome, and they are greatly appreciated! Every little bit helps, and credit will always be given.

You can contribute in many ways:

---

## 🚀 Ways to Contribute

---

## ⚙️ Get Started

1. **Fork the repo**
2. **Clone your fork**

    ```bash
    git clone git@github.com:your_name_here/sharc.git
    cd SHARC/
    ```

3. **Set up a virtual environment (Python 3.8+)**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

4. **Install dependencies**

    ```bash
    pip install -r requirements.txt
    ```

5. **Install SHARC in editable mode**

    ```bash
    pip install -e .
    ```

6. **Create a new branch**

    ```bash
    git checkout -b name-of-your-bugfix-or-feature
    ```
---

### 🐛 Report Bugs
Spotted a bug? Please report it at [SHARC Issues](https://github.com/Radio-Spectrum/SHARC/issues)

Include the following:
- Your OS name and version
- Python version and dependencies
- Steps to reproduce the bug

---

### 🔧 Fix Bugs
Check for open [issues](https://github.com/Radio-Spectrum/SHARC/issues) tagged with `bug` and `help wanted`. Feel free to take one on and submit a fix!

---

### ✨ Implement Features
Want to add a new antenna or propagation model? Browse the issues labeled `enhancement` and `help wanted`.

---

### 📝 Write Documentation
We welcome contributions to:
- Official documentation
- Docstrings
- Blog posts and tutorials

If you add a new feature, please update the Wiki or relevant documentation files.

---

### 💡 Submit Feedback
Have an idea or suggestion? Open a feature request at [SHARC Issues](https://github.com/Radio-Spectrum/SHARC/issues)

Feature requests should:
- Clearly explain the functionality
- Keep the scope narrow
- Remember this is a volunteer-driven project

---

## 🌱 Branching Model

SHARC follows the Git flow model: [A Successful Git Branching Model](https://nvie.com/posts/a-successful-git-branching-model/)

### 🔀 Main Branches

- `master`: Stable, production-ready code
- `development`: Latest development changes for upcoming releases

When `development` is stable, it is merged into `master` and tagged.

---

### 🌿 Supporting Branches

| Branch Type   | From         | To                 | Naming Example              |
|---------------|--------------|--------------------|-----------------------------|
| Feature       | `development`| `development`      | `feat/new-propagation`   |
| Release       | `development`| `development`, `master` | `release/1.0.0`        |
| Hotfix        | `master`     | `development`, `master` | `hotfix/fix-crash`     |

---

## 🧠 Code Guidelines

### 🐍 Python Style

- Follow [PEP8](https://peps.python.org/pep-0008/)
- Use type annotations  
  See: [Python Type Hints Cheat Sheet](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)

---

### 📚 Docstrings

- Use **Google-style** docstrings
- Keep them updated when making changes
- Example:

    ```python
    def foo(arg1: str) -> int:
        """Returns the length of arg1.

        Args:
            arg1 (str): The string to calculate the length of.

        Returns:
            int: The length of the provided string.
        """
        return len(arg1)
    ```

For VSCode users: try the *Python Docstring Generator* plugin.

---

## ✅ Testing Your Changes

1. **Lint with flake8**

    ```bash
    flake8 sharc tests
    ```

2. **Run tests**

    ```bash
    python setup.py test
    # OR
    py.test
    ```

3. **Install testing tools if needed**

    ```bash
    pip install flake8 tox
    ```

---

## 📦 Submitting Changes

1. **Commit**

    ```bash
    git add .
    git commit -m "Detailed description of your changes"
    ```

2. **Push**

    ```bash
    git push origin name-of-your-bugfix-or-feature
    ```

3. **Open a Pull Request**

Make sure:
- Your PR includes tests
- Documentation is updated
- Code works with Python 2.6, 2.7, 3.3–3.5, and PyPy  

---

## 🧪 Running a Subset of Tests

```bash
py.test tests.test_sharc
