import discord
from discord.ext import commands

import json
import asyncio


with open("config.json") as config_file:
    config = json.load(config_file)

async def open_current_data():
    with open("cogs/current_data.json") as current_data_file:
        current_data = json.load(current_data_file)
        return current_data


class MyBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="#",
            intents=discord.Intents.all(),
            application_id=config["APPLICATION_ID"]
        )
        self.synced = True

    async def setup_hook(self):
        extensions = ["commands", "administration"]
        for extension in extensions:
            await self.load_extension(f"cogs.{extension}")
            print(f"Added cog '{extension}'")

    async def on_ready(self):
        print(f"Logged in as {self.user}!")

    async def on_guild_join(self, guild):
        print(f"Joined {guild.name} ({guild.id})")
        current_data = await open_current_data()
        current_data["servers"][guild.id] = {"restricted_users": []}
        with open("cogs/current_data.json", "w") as json_file:
            json.dump(current_data, json_file, indent=4)


bot = MyBot()


bot.run(config["TOKEN"])
