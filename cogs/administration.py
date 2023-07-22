import discord
from discord.ext import commands
from discord import app_commands

class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, ctx):
        if (ctx.author.id in [807602307369271306]) and (isinstance(ctx.channel, discord.DMChannel)):
            if ctx.content.lower() in ["synccommandtree", "sync", "sct"]:
                await self.bot.tree.sync()
                await ctx.channel.send("Done!")
                print("The command tree was synced")

            elif ctx.content.lower() == "shutdown":
                exit(f"Shut down by {ctx.author.name}")


async def setup(bot):
    await bot.add_cog(
        Administration(bot)
    )
