# Mafia Game Telegram Bot

This bot enable hosting and managing Mafia games on Telegram.

---

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [File Structure](#file-structure)
- [Changelog](#changelog)
- [License](#license)

---

## Introduction

The Mafia Game Telegram Bot is designed to simplify the process of hosting and managing Mafia-style games directly on Telegram. In this major update, we’ve reworked many functionalities, improved reliability, and added interactive features to enhance your gaming experience.

---

## Features

- **Game Creation & Joining:**
  - Create a new game with a unique passcode.
  - Join existing games securely via passcode verification.
  
- **Interactive Role Management:**
  - Set roles with intuitive inline buttons.
  - Automatically assign roles using the Random.org API for true randomness with a local fallback.
  - Save and manage role templates (with maintainer confirmation) for recurring game setups.
  
- **Player Management:**
  - Eliminate or revive players during the game.
  - Real-time updates to player statuses in the database.
  
- **Advanced Voting System:**
  - Engage in both regular and anonymous voting sessions.
  - Toggle voting permissions: control who can vote and be voted.
  - Receive detailed voting summaries and a comprehensive, real-time voting report.
  
- **Inquiry & Reporting:**
  - Generate faction summaries and detailed inquiry reports.
  - Receive individual role and game status notifications.
  
- **Robust Database & Logging:**
  - Uses SQLite with Write-Ahead Logging (WAL) for efficient concurrent access.
  - Automatic migrations and schema updates.
  - Comprehensive logging throughout the system for easy troubleshooting.

---

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/the-mahdi/Mafia_bot
   cd Mafia_bot
   ```

2. **Set Up a Virtual Environment (Recommended):**

   ```bash
   python3 -m venv venv
   source venv/bin/activate    # On Windows, use: venv\Scripts\activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Docker Deployment (Optional):**
   - Use the provided `docker-compose.yml` and `dockerfile` for containerized deployment:
     ```bash
     docker-compose up --build
     ```

---

## Configuration

1. **Tokens & API Keys:**
   - Create a `token.txt` file inside the `data` directory with the following three lines:
     ```
     YOUR_TELEGRAM_BOT_TOKEN
     YOUR_RANDOM_ORG_API_KEY
     YOUR_MAINTAINER_TELEGRAM_ID
     ```
   - These tokens are used for authenticating your bot, accessing the Random.org API for randomness, and managing role template confirmations.

2. **Roles & Templates:**
   - Define available roles and their descriptions in `data/roles.json`.
   - Role templates can be saved in `data/role_templates.json` and will require maintainer confirmation before becoming active.

3. **Database:**
   - The bot uses an SQLite database (`db/mafia_game.db`) which is created and updated automatically on the first run.

---

## Usage

1. **Starting the Bot:**
   - Run the bot using:
     ```bash
     python main.py
     ```
   - Alternatively, deploy with Docker as described above.

2. **Interacting with the Bot:**
   - Use the `/start` command to begin.
   - **Game Options:**
     - **Create Game:** Generates a unique passcode to start a new game.
     - **Join Game:** Enter a passcode to join an existing game.
     - **Set Roles / Select Template:** Use inline buttons to adjust role counts and apply role templates.
     - **Manage Games:** Access functionalities for eliminating/reviving players, starting games, and configuring voting sessions.
   - **Voting & Inquiry:**
     - Participate in interactive voting sessions with both public and anonymous modes.
     - Receive detailed voting summaries and inquiry reports on faction and role distributions.

---

## File Structure

```
Mafia_bot/
├── docker-compose.yml
├── dockerfile
├── LICENSE.txt
├── main.py
├── readme.md
├── requirements.txt
├── data/
│   ├── token.txt
│   ├── roles.json
│   └── role_templates.json
├── db/
│   └── mafia_game.db      # Auto-generated on first run
└── src/
    ├── config.py
    ├── db.py
    ├── roles.py
    ├── utils.py
    ├── handlers/
    │   ├── start_handler.py
    │   ├── passcode_handler.py
    │   ├── button_handler.py
    │   └── game_management/
    │       ├── base.py
    │       ├── create_game.py
    │       ├── join_game.py
    │       ├── start_game.py
    │       ├── roles_setup.py
    │       ├── player_management.py
    │       ├── voting.py
    │       └── inquiry.py
    └── __init__.py
```

---

## Changelog

- **Role Assignment Enhancements:**
  - Integrated Random.org API to improve role assignment randomness.
  - Added local fallback using Python’s built-in random module.
- **Interactive UI Upgrades:**
  - Redesigned inline keyboard interfaces for setting roles, managing games, and voting.
- **Advanced Voting System:**
  - Introduced anonymous voting mode.
  - Implemented voting permissions to control who can vote and be voted.
  - Detailed voting summaries and a full voting report now available.
- **Player Management Improvements:**
  - Added functionalities for eliminating and reviving players mid-game.
  - Implemented maintainer confirmation for new role templates.
- **Database & Logging:**
  - Enhanced database schema with automatic migration and WAL mode.
  - Improved logging across modules for better debugging and monitoring.

---

## License

This project is licensed under the [MIT License](LICENSE.txt).

---