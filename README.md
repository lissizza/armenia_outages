# Armenia Outages Watcher

Armenia Outages Watcher is a Telegram bot designed to monitor and notify users about power, water, and gas outages in Armenia. The bot supports multiple languages (Armenian, Russian, and English) and allows users to subscribe to outage notifications for specific areas. The project is built using Python based on `python-telegram-bot`.

## Features

- **Multi-language support:** The bot provides notifications in Armenian, Russian, and English.
- **Real-time updates:** Periodically checks for power, water, and gas (not implemented) outages and posts updates to specified Telegram channels.
- **User subscriptions:** Users can subscribe to specific areas and receive notifications about outages in those areas (not yet fully implemented).

## Installation

### Prerequisites

- Python 3.8 or higher (developed on 3.12)
- Docker and Docker Compose

### Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/lissizza/armenia-outages.git
   cd armenia-outages
   ```

2. **Configure the environment variables:**

   Create a `.env` file in the root directory of the project and add the following variables:

   ```plaintext
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   OPENAI_AI_KEY=your_openai_key
   POSTGRES_USER=your_postgres_username
   POSTGRES_PASSWORD=your_postgres_password
   DATABASE_URL=postgresql+asyncpg://your_user:your_password@db:5432/armenia_outages
   SYNC_DATABASE_URL=postgresql+psycopg2://your_user:your_password@armenia-db:5432/armenia_outages
   POSTGRES_PORT=5432
   ```

3. **Build and run the containers:**

   In the root directory of the project, run:

   ```bash
   docker-compose up --build -d
   ```

   This command will build the necessary Docker images and start the containers in detached mode. The environment variables will be automatically loaded from the `.env` file.

4. **Initialize the database:**

   If the database has not been initialized, you can run the following command inside the running container:

   ```bash
   docker-compose exec bot python3 -m db init_db
   ```

   This will create the necessary database tables.

## Usage

- **Start the bot:** Users can start the bot by sending the `/start` command.
- **Set language:** The bot will prompt the user to select their preferred language.
- **Subscribe to notifications:** Users can subscribe to specific areas by providing a keyword or selecting from a list.
- **List subscriptions:** The `/subscription_list` command will list all the user's current subscriptions and allows to unsubscribe.

## Future Plans

- **Planned Power Outage Parser:** The parser for planned power outages is currently under development and will be implemented in future versions.
- **Subscription Handling:** While subscriptions are being created, the functionality to handle and filter notifications based on subscriptions is still in progress.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue on GitHub.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
