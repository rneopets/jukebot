import asyncio
import contextlib
import ctypes.util
import logging
import os
import sys
from collections import defaultdict
from collections.abc import Generator
from logging.handlers import RotatingFileHandler
from typing import Any

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

discord.opus.load_opus(ctypes.util.find_library("opus"))  # type: ignore

intents = discord.Intents.none()
intents.voice_states = True
intents.guilds = True
intents.message_content = True
intents.guild_messages = True

initial_extensions = [
    "cogs.music",
    "cogs.debug",
]


@contextlib.contextmanager
def setup_logging() -> Generator[None]:
    try:
        # __enter__
        max_bytes = 32 * 1024 * 1024  # 32 MiB
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("discord.http").setLevel(logging.WARNING)

        log = logging.getLogger()
        log.setLevel(logging.INFO)
        handler = RotatingFileHandler(
            filename="bot.log",
            encoding="utf-8",
            mode="w",
            maxBytes=max_bytes,
            backupCount=2,
        )
        dt_fmt = "%Y-%m-%d %H:%M:%S"
        fmt = logging.Formatter(
            "[{asctime}] [{levelname:<7}] {name}: {message}",
            dt_fmt,
            style="{",
        )
        handler.setFormatter(fmt)
        log.addHandler(handler)

        yield
    finally:
        # __exit__
        handlers = log.handlers[:]  # type: ignore
        for hdlr in handlers:
            hdlr.close()
            log.removeHandler(hdlr)  # type: ignore


class Jukebot(commands.Bot):
    initial_extensions: list[str]
    currently_playing: defaultdict[int, str]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.initial_extensions = initial_extensions
        self.currently_playing = defaultdict(str)

    async def start_extensions(self) -> None:
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
            except Exception as e:
                import traceback

                traceback.print_exc()
                print(f"Failed to load extension {extension}\n{type(e).__name__}: {e}")

    async def setup_hook(self) -> None:
        assert self.user is not None

        print(f"Logged in as {self.user} (ID: {self.user.id})")
        self.bot_app_info = await self.application_info()
        self.owner_id = self.bot_app_info.owner.id

        try:
            await self.start_extensions()
        except Exception:
            import traceback

            traceback.print_exc()
            sys.exit(1)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        await self.process_commands(message)


async def main() -> None:
    with setup_logging():
        bot = Jukebot(
            max_messages=None,
            command_prefix=commands.when_mentioned_or("$"),
            intents=intents,
        )
        async with bot:
            await bot.start(os.getenv("BOT_TOKEN"))  # type: ignore


if __name__ == "__main__":  # so this doesn't get run when we import it
    asyncio.run(main())
