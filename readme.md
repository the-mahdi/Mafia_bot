# Mafia Game Telegram Bot

Welcome to the Mafia Game Telegram Bot, a feature-rich bot designed to facilitate and manage Mafia-style games directly within Telegram. Whether you're hosting a small group or a large gathering, this bot streamlines the process of creating games, managing players, assigning roles, and ensuring fair play through robust randomness mechanisms.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [File Structure](#file-structure)
- [Database Schema](#database-schema)

## Features
- Create and Manage Games: Easily create new Mafia games with unique passcodes and manage existing games.
- Join Games: Players can join games using a passcode, ensuring only invited participants can join.
- Role Assignment: Assign roles to players using either the Random.org API for true randomness or a local fallback method.
- Interactive Role Management: Use Telegram's inline buttons to set, adjust, and confirm roles within the game.
- Secure and Concurrent Database Handling: Utilizes SQLite with Write-Ahead Logging (WAL) for efficient and safe concurrent operations.
- Comprehensive Logging: Detailed logs to monitor bot activities and troubleshoot issues.

## Prerequisites
Before setting up the Mafia Game Telegram Bot, ensure you have the following:

- Python 3.12 or higher: The bot is built using Python. You can download it from [python.org](https://www.python.org/).
- Telegram Bot Token: Obtain a token by creating a new bot via BotFather on Telegram.
- Random.org API Key: Sign up for an API key at [Random.org](https://www.random.org/).

## Installation

1. Clone the repository and navigate to it.
   ```bash
   git clone https://github.com/the-mahdi/Mafia_bot.git
   cd project_location 
   ```

2. Create a Virtual Environment (Optional but Recommended)
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows, use venv\Scripts\activate
   ```

3. Install Dependencies
   Ensure you have pip installed. Then run:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### 1. Setting Up token.txt
Create a file named `token.txt` in the root directory of the project with the following structure:

```
YOUR_TELEGRAM_BOT_TOKEN
YOUR_RANDOM_ORG_API_KEY
```

- First Line: Your Telegram Bot Token obtained from BotFather.
- Second Line: Your Random.org API Key.

Example:
```
123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ
abcdef12-3456-7890-abcd-ef1234567890
```

### 2. Defining Roles

#### a. list_roles.txt
List all the roles available in your Mafia game, one per line.

Example:
```
ShahrSaD
Doctor
```

#### b. role_descriptions.txt
Provide descriptions for each role in the following format:

```
RoleName: Description of the role.
```

Example:
```
ShahrSaD: The "Shahr Sade" is a simple citizen ...
Doctor: The Doctor has the ability to save one person each night from ...

```

Ensure that every role listed in `list_roles.txt` has a corresponding description in `role_descriptions.txt`. If a description is missing, the bot will assign a default message indicating that no description is available.

### 3. Database Setup
The bot uses SQLite for data storage. Upon first run, it will automatically create a `mafia_game.db` file with the necessary tables:

- Users: Stores user information.
- Games: Stores game details.
- Roles: Assigns roles to users within a game.
- GameRoles: Manages the count of each role within a game.

## Usage

1. Start the Bot
   Run the bot using:
   ```bash
   python mafia_bot.py
   ```

2. Interact with the Bot on Telegram
   - `/start`: Begin interacting with the bot. You'll be presented with options to create or join a game.
   - Create Game: Generates a unique passcode for a new game. Share this passcode with players you want to join.
   - Join Game: Enter the passcode to join an existing game.
   - Set Roles: As a moderator, set the number of each role available in the game using interactive buttons.
   - Start Game: Once all roles are set and players have joined, start the game. Players will receive their assigned roles via private messages.

3. Role Assignment
   The bot attempts to use the Random.org API to shuffle and assign roles for true randomness. If the API call fails, it falls back to Python's local random module to ensure continuity.

4. Logging
   The bot logs its activities to the console.

## File Structure
```
mafia-game-telegram-bot/
│
├── list_roles.txt           # List of available roles, one per line.
├── role_descriptions.txt    # Descriptions for each role in "Role: Description" format.
├── requirements.txt         # Python dependencies.
├── token.txt                # Telegram and Random.org API tokens (see Configuration).
├── mafia_game.db            # SQLite database (auto-generated on first run).
└── mafia_bot.py             # Main Python script for the bot.
```

### requirements.txt
Ensure all necessary Python packages are installed. Below is an example of what your `requirements.txt` might include:

```
aiohappyeyeballs==2.4.3
aiohttp==3.10.9
aiosignal==1.3.1
```


## Database Schema
The bot uses SQLite with the following tables:

### Users
| Column       | Type      | Description                           |
|--------------|-----------|---------------------------------------|
| user_id      | INTEGER   | Primary key (Telegram user ID).       |
| username     | TEXT      | Telegram username.                    |
| last_updated | TIMESTAMP | Timestamp of the last update.         |

### Games
| Column            | Type    | Description                                               |
|-------------------|---------|-----------------------------------------------------------|
| game_id           | INTEGER | Primary key (Auto-incremented).                           |
| passcode          | TEXT    | Unique passcode for the game.                             |
| moderator_id      | INTEGER | User ID of the game moderator.                            |
| started           | INTEGER | Flag indicating if the game has started (0 or 1).         |
| randomness_method | TEXT    | Method used for randomness ("Random.org" or fallback).    |

### Roles
| Column  | Type    | Description                                     |
|---------|---------|--------------------------------------------------|
| game_id | INTEGER | Foreign key referencing Games(game_id).          |
| user_id | INTEGER | Foreign key referencing Users(user_id).          |
| role    | TEXT    | Assigned role to the user in the game.           |

Primary Key: (game_id, user_id)

### GameRoles
| Column  | Type    | Description                                     |
|---------|---------|--------------------------------------------------|
| game_id | INTEGER | Foreign key referencing Games(game_id).          |
| role    | TEXT    | Role name.                                       |
| count   | INTEGER | Number of players assigned to this role.         |

Primary Key: (game_id, role)