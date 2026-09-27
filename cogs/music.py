import asyncio
import random
from pathlib import Path

import discord
from discord.ext import commands, tasks

from jukebot import Jukebot

NEO_JUKEBOX = 1077343507343212585
MOD_VOICE_CHAT = 1134620255155650622
ALLOWED_VOICE_CHANNELS = (NEO_JUKEBOX, MOD_VOICE_CHAT)
MUSIC_DIR = Path("./music")


def get_song_index(songs: list[str], song_name: str) -> int | None:
    """Returns the index of the song in the list of songs"""
    try:
        return songs.index(song_name)
    except ValueError:
        return None


def get_songs() -> list[str]:
    """Returns a list of all mp3 files in the music directory"""
    # because doing this at module level isn't great when I add songs at runtime
    return list(sorted(p.name for p in Path(MUSIC_DIR).glob("**/*.mp3")))


async def songs_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    songs = get_songs()

    if not current:
        # if the user hasn't typed anything yet, shuffle the songs so they come up randomly
        # this is better than just showing the top alphabetical songs for visibility purposes.
        random.shuffle(songs)

    filtered_songs = [s for s in songs if s.lower().startswith(current.lower())][:25]

    return [
        discord.app_commands.Choice(name=Path(s).stem, value=s) for s in filtered_songs
    ]


class Music(commands.Cog):
    def __init__(self, bot: Jukebot) -> None:
        self.bot = bot
        self.check_voice.start()

    @tasks.loop(seconds=15)
    async def check_voice(self) -> None:
        """Checks if the bot is alone in a voice channel and disconnects if so"""
        await self.bot.wait_until_ready()
        for vc in self.bot.voice_clients:
            if len(vc.channel.members) == 1:  # type: ignore
                asyncio.create_task(vc.disconnect(force=True))

    async def cog_unload(self) -> None:
        self.check_voice.stop()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        assert self.bot.user is not None

        if member.id == self.bot.user.id:
            # ignore the bot's own voice state changes
            return

        # connect to the voice channel if the bot is not in it and someone else is in it
        if (
            after.channel is not None
            and after.channel.id == NEO_JUKEBOX
            and after.channel.guild.voice_client is None
        ):
            await after.channel.connect()

    async def play_song(
        self, interaction: discord.Interaction, *, song_path: str
    ) -> None:
        """Plays a song from the local filesystem"""
        assert interaction.guild is not None
        assert interaction.guild.voice_client is not None

        song_file = MUSIC_DIR / song_path

        # to keep state of what's playing (or last played,) in which server
        self.bot.currently_playing[interaction.guild.id] = song_file.name

        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                str(song_file),
                before_options="-stream_loop -1",  # loop forever
            )
        )

        interaction.guild.voice_client.play(  # type: ignore
            source,
            after=lambda e: print(f"Player error: {e}") if e else None,  # type: ignore
        )

        await interaction.response.send_message(
            f"Now playing: `{song_file.stem}` \N{MULTIPLE MUSICAL NOTES}",
        )

    @discord.app_commands.command(
        name="play", description="Plays a song from the local filesystem"
    )
    @discord.app_commands.autocomplete(song=songs_autocomplete)
    @discord.app_commands.describe(song="The Neopets song you're looking for")
    async def play_slash(self, interaction: discord.Interaction, song: str) -> None:
        if song not in get_songs():
            await interaction.response.send_message(
                f"Song `{song}` not found.", ephemeral=True
            )
            return
        await self.ensure_voice(interaction)
        await self.play_song(interaction, song_path=song)

    @discord.app_commands.command(
        name="next", description="Plays the next song in the local filesystem"
    )
    async def next_slash(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        await self.ensure_voice(interaction)
        songs = get_songs()
        current_song = self.bot.currently_playing[interaction.guild.id]

        current_song_index = get_song_index(songs, current_song)
        if current_song_index is None:
            current_song_index = -1

        song = songs[(current_song_index + 1) % len(songs)]
        await self.play_song(interaction, song_path=song)

    @discord.app_commands.command(
        name="previous", description="Plays the previous song in the local filesystem"
    )
    async def previous_slash(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        await self.ensure_voice(interaction)
        songs = get_songs()
        current_song = self.bot.currently_playing[interaction.guild.id]

        current_song_index = get_song_index(songs, current_song) or 0

        song = songs[current_song_index - 1]
        await self.play_song(interaction, song_path=song)

    @discord.app_commands.command(
        name="shuffle", description="Plays a random song in the local filesystem"
    )
    async def shuffle_slash(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        await self.ensure_voice(interaction)
        songs = get_songs()

        current_song = self.bot.currently_playing[interaction.guild.id]

        current_song_index = get_song_index(songs, current_song)
        if current_song_index is not None:
            songs.pop(current_song_index)

        song = random.choice(songs)
        await self.play_song(interaction, song_path=song)

    @discord.app_commands.command(
        name="stop",
        description="Stops playback and disconnects the bot from the voice channel",
    )
    async def stop_slash(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None

        if interaction.guild.voice_client is None:
            await interaction.response.send_message(
                "I'm not connected to a voice channel.", ephemeral=True
            )
            return

        assert isinstance(interaction.user, discord.Member)
        bot_channel = interaction.guild.voice_client.channel  # type: ignore
        if (
            interaction.user.voice is None
            or interaction.user.voice.channel is None
            or interaction.user.voice.channel.id != bot_channel.id
        ):
            await interaction.response.send_message(
                f"You need to be in <#{bot_channel.id}> to do that.", ephemeral=True
            )
            return

        await interaction.guild.voice_client.disconnect(force=True)
        await interaction.response.send_message(
            "Stopped playback and left the voice channel. \N{OCTAGONAL SIGN}"
        )

    async def ensure_voice(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None

        if interaction.guild.voice_client is None:
            assert interaction.user is not None
            assert isinstance(interaction.user, discord.Member)
            if interaction.user.voice:
                assert interaction.user.voice.channel is not None

                if interaction.user.voice.channel.id not in ALLOWED_VOICE_CHANNELS:
                    allowed_channels = " or ".join(
                        f"<#{channel_id}>" for channel_id in ALLOWED_VOICE_CHANNELS
                    )
                    await interaction.response.send_message(
                        f"You are not in {allowed_channels}.", ephemeral=True
                    )
                    raise commands.CommandError("Author not in an allowed voice channel.")
                await interaction.user.voice.channel.connect()
            else:
                await interaction.response.send_message(
                    f"You are not connected to a voice channel. Join <#{NEO_JUKEBOX}>!",
                    ephemeral=True,
                )
                raise commands.CommandError("Author not connected to a voice channel.")
        else:
            assert isinstance(interaction.user, discord.Member)
            bot_channel = interaction.guild.voice_client.channel  # type: ignore
            if (
                interaction.user.voice is None
                or interaction.user.voice.channel is None
                or interaction.user.voice.channel.id != bot_channel.id
            ):
                await interaction.response.send_message(
                    f"You need to be in <#{bot_channel.id}> to do that.", ephemeral=True
                )
                raise commands.CommandError("Author not in the bot's voice channel.")
            if interaction.guild.voice_client.is_playing():  # type: ignore
                interaction.guild.voice_client.stop()  # type: ignore


async def setup(bot: Jukebot) -> None:
    await bot.add_cog(Music(bot))
