import discord
from discord.ext import commands
from discord import app_commands

import json
import requests
import asyncio
from io import BytesIO
import urllib.parse


async def open_current_data():
    with open("cogs/current_data.json") as f:
        current_data = json.load(f)
        return current_data

async def open_config():
    with open("config.json") as f:
        config = json.load(f)
        return config

async def update_current_data(current_data):
    with open("cogs/current_data.json", "w") as json_file:
        json.dump(current_data, json_file, indent=4)


class BotCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def get_location_id(interaction):
        location_id = f"{interaction.guild_id}-{interaction.channel.id}"
        return location_id

    async def get_amount_of_teams(self, location_id):
        current_data = await open_current_data()
        return await self.convert_format_to_amount_of_teams(current_data["current_locations"][location_id]["format"])

    @staticmethod
    async def get_current_race(location_id):
        current_data = await open_current_data()
        return current_data["current_locations"][location_id]["current_race"]

    @staticmethod
    async def get_table_image(location_id, current_race=None):
        base_url_lorenzi = "https://gb.hlorenzi.com/table.png?data="
        current_data = await open_current_data()
        if current_race is None:
            current_race = current_data["current_locations"][location_id]["current_race"]
        teams = current_data["current_locations"][location_id]["teams"]
        table_text = f"#title Standings after race {current_race + 1}"
        for team in teams:
            tag = teams[team]["tag"]
            score = teams[team]["total_score"]
            table_text += f"\n{tag} {score}"
        encoded_table_text = urllib.parse.quote(table_text)
        link = base_url_lorenzi + encoded_table_text
        print(link)
        table_data = requests.get(link)
        table_bytes = BytesIO(table_data.content)
        return table_bytes

    @staticmethod
    async def set_race(location_id, new_race):
        current_data = await open_current_data()
        current_data["current_locations"][location_id]["current_race"] = new_race
        await update_current_data(current_data)

    @staticmethod
    async def check_for_mod_permission(interaction, user):
        permissions = interaction.channel.permissions_for(user)
        if permissions.manage_messages:
            return True
        return False

    @staticmethod
    async def check_for_valid_user(server_id, user):
        current_data = await open_current_data()
        invalid_users = current_data["servers"][server_id]["restricted_users"]
        if user.id in invalid_users:
            return False
        return True

    @staticmethod
    async def check_if_mogi_is_currently_going(location_id):
        current_data = await open_current_data()
        return current_data["current_locations"].get(location_id) is not None

    @staticmethod
    async def check_format(format):
        if format not in [2, 3, 4, 6]:
            return "This is an invalid format!"
        elif format == 6:
            return "Use the Toadbot for 6v6 mogis!"
        return True

    async def check_tags(self, tags_string, format):
        amount_of_tags = await self.convert_format_to_amount_of_teams(format)
        tags = tags_string.split(" ")
        if len(tags) != amount_of_tags:
            return "The amount of tags doesnt fit with the format!"
        if len(set(tags)) != amount_of_tags:
            return "Duplicate tags aren't allowed!"
        return True

    @staticmethod
    async def check_race(race):
        check = race in range(13)
        if not check:
            return "Your race must be between 1 and 12"
        return True

    async def check_for_correct_tag(self, tag, location_id):
        current_data = await open_current_data()
        all_tags = []
        for team_nr in range(await self.convert_format_to_amount_of_teams(current_data["current_locations"][location_id]["format"])):
            all_tags.append(current_data["current_locations"][location_id]["teams"][f"team{team_nr}"]["tag"])
        if tag in all_tags:
            return True
        return "There is no team with this tag in the mogi! You can use the command `/edit_tag` to change a tag"

    @staticmethod
    async def check_for_correct_spots(spots, location_id):
        current_data = await open_current_data()
        format = current_data["current_locations"][location_id]["format"]
        spots_lst = spots.split(" ")
        if len(spots_lst) == format:
            return True
        return "The amount of spots don't match with the format!"

    @staticmethod
    async def check_for_amount_of_entered_spots(location_id, current_race=None):
        current_data = await open_current_data()
        if current_race is None:
            current_race = current_data["current_locations"][location_id]["current_race"]
        race_scores = current_data["current_locations"][location_id]["races"][f"race{current_race}"]
        entered_spots = 0
        for scores in race_scores.values():
            if len(scores) != 0:
                entered_spots += 1
        return entered_spots

    @staticmethod
    async def check_for_teams_missing(location_id, current_race=None):
        current_data = await open_current_data()
        if current_race is None:
            current_race = current_data["current_locations"][location_id]["current_race"]
        race_scores = current_data["current_locations"][location_id]["races"][f"race{current_race}"]
        missing_teams = []
        for team, scores in race_scores.items():
            if len(scores) == 0:
                missing_teams.append(team)
        missing_tags = []
        for team in missing_teams:
            missing_tags.append(current_data["current_locations"][location_id]["teams"][team]["tag"])
        return missing_tags

    @staticmethod
    async def check_for_human_spot_errors(location_id):
        current_data = await open_current_data()
        races = current_data["current_locations"][location_id]["races"]
        all_errors = {}
        for race in races:
            all_spots = []
            for team in races[race]:
                all_spots.extend(races[race][team])
            if len(all_spots) == 0:
                continue
            all_errors[race] = {"missing_spots": [], "duplicate_spots": set()}
            for spot in range(1, 13):
                if spot not in all_spots:
                    all_errors[race]["missing_spots"].append(spot)
            duplicates = [spot for spot in all_spots if all_spots.count(spot) > 1]
            all_errors[race]["duplicate_spots"].update(duplicates)
            if len(all_errors[race]["missing_spots"]) == 0:
                del all_errors[race]
        if len(all_errors) != 0:
            return all_errors
        return False

    async def check_for_spots_already_entered(self, location_id, team, race=None):
        current_data = await open_current_data()
        if race is None:
            race = current_data["current_locations"][location_id]["current_race"]
        team = await self.convert_tag_to_team_number(location_id, team)
        if len(current_data["current_locations"][location_id]["races"][f"race{race}"][f"team{team}"]) == 0:
            return False
        return True

    @staticmethod
    async def check_if_tag_exists(location_id, tag):
        current_data = await open_current_data()
        for team in current_data["current_locations"][location_id]["teams"]:
            if current_data["current_locations"][location_id]["teams"][team]["tag"] == tag:
                return True
        return False

    @staticmethod
    async def convert_format_to_amount_of_teams(format):
        convertion = {
            "2": 6,
            "3": 4,
            "4": 3
        }
        return convertion[str(format)]

    @staticmethod
    async def convert_spot_to_points(spot):
        spot_to_points = {
            1: 15,
            2: 12,
            3: 10,
            4: 9,
            5: 8,
            6: 7,
            7: 6,
            8: 5,
            9: 4,
            10: 3,
            11: 2,
            12: 1
        }
        return spot_to_points[spot]

    @staticmethod
    async def convert_tag_to_team_number(location_id, tag):
        current_data = await open_current_data()
        for number, team in enumerate(current_data["current_locations"][location_id]["teams"]):
            if current_data["current_locations"][location_id]["teams"][team]["tag"] == tag:
                return number

    async def add_new_location_to_json(self, location_id, format, tags):
        current_data = await open_current_data()
        amount_of_teams = await self.convert_format_to_amount_of_teams(format)
        current_data["current_locations"][location_id] = {"teams": {}, "races": {}, "format": format, "current_race": 0}
        for index, tag in enumerate(tags):
            current_data["current_locations"][location_id]["teams"][f"team{index}"] = {"tag": tag, "total_score": 0}
        for race in range(12):
            current_data["current_locations"][location_id]["races"][f"race{race}"] = {}
            for team in range(amount_of_teams):
                current_data["current_locations"][location_id]["races"][f"race{race}"][f"team{team}"] = []
        await update_current_data(current_data)

    async def enter_spots_to_data(self, location_id, tag, spots, race=None):
        current_data = await open_current_data()
        if race is None:
            race = current_data["current_locations"][location_id]["current_race"]
        current_data["current_locations"][location_id]["races"][f"race{race}"][f"team{await self.convert_tag_to_team_number(location_id, tag)}"] = spots
        await update_current_data(current_data)

    @staticmethod
    async def automatically_enter_score_of_last_team(location_id, current_race=None):
        current_data = await open_current_data()
        if current_race is not None:
            current_race = current_data["current_locations"][location_id]["current_race"]
        current_race_scores = current_data["current_locations"][location_id]["races"][f"race{current_race}"]
        all_entered_scores = []
        missing_team = None
        for team in current_race_scores:
            if len(current_race_scores[team]) == 0:
                missing_team = team
                continue
            all_entered_scores.extend(current_race_scores[team])
        all_supposed_scores = list(range(1, 13))
        missing_scores = [list(set(all_supposed_scores) - set(all_entered_scores))]
        amount_of_spots = int(12/len(current_race_scores))
        current_data["current_locations"][location_id]["races"][f"race{current_race}"][missing_team] = missing_scores[0][:amount_of_spots]
        await update_current_data(current_data)

    async def edit_total_scores(self, location_id):
        current_data = await open_current_data()
        total_scores = {}
        for team in current_data["current_locations"][location_id]["teams"]:
            total_scores[team] = 0
        for team in total_scores:
            for race in current_data["current_locations"][location_id]["races"]:
                for spot in current_data["current_locations"][location_id]["races"][race][team]:
                    total_scores[team] += await self.convert_spot_to_points(spot)
        for team in current_data["current_locations"][location_id]["teams"]:
            current_data["current_locations"][location_id]["teams"][team]["total_score"] = total_scores[team]
        await update_current_data(current_data)

    @staticmethod
    async def write_human_spot_error_message(location_id, errors):
        current_data = await open_current_data()
        error_message = f"```ini\n"
        teams_with_errors = set()
        for race in errors:
            race_number = str(int(race[4:]) + 1)
            error_message += f"Race {race_number}\n"
            teams = current_data["current_locations"][location_id]["races"][race]
            for team in teams:
                team_score_message_part = ""
                team_score_message_part += f"{current_data['current_locations'][location_id]['teams'][team]['tag']}: "
                team_scores = current_data["current_locations"][location_id]["races"][race][team]
                for spot in team_scores:
                    if spot in errors[race]["duplicate_spots"]:
                        spot_msg = f"[{str(spot)}]"
                        teams_with_errors.update(current_data['current_locations'][location_id]['teams'][team]['tag'])
                    else:
                        spot_msg = str(spot)
                    team_score_message_part += f"{spot_msg} "
                error_message += f"{team_score_message_part}\n"
            error_message += f"Missing spots: {', '.join([str(spot) for spot in errors[race]['missing_spots']])}\n\n"
        error_message += "```\n"
        if len(teams_with_errors) != 0:
            error_message += "Please edit your spots: " + ", ".join(list(teams_with_errors))
        return error_message

    @staticmethod
    async def write_entry_error_message(errors, race):
        error_message = "The spot"
        if len(errors[f"race{race}"]["duplicate_spots"]) != 1:
            error_message += "s"
        error_message += " "
        error_message += ", ".join(str(spot) for spot in errors[f"race{race}"]["duplicate_spots"])
        if len(errors[f"race{race}"]["duplicate_spots"]) == 1:
            error_message += " was "
        else:
            error_message += " were "
        error_message += "already entered, check for errors please! Use `/edit_spots` to correct them"
        return error_message

    @staticmethod
    async def change_tag(location_id, old_tag, new_tag):
        current_data = await open_current_data()
        for team in current_data["current_locations"][location_id]["teams"]:
            if current_data["current_locations"][location_id]["teams"][team]["tag"] == old_tag:
                current_data["current_locations"][location_id]["teams"][team]["tag"] = new_tag
                break
        await update_current_data(current_data)
        return

    async def set_race_to_default(self, location_id, race):
        current_data = await open_current_data()
        default_standings = {}
        amount_of_teams = await self.convert_format_to_amount_of_teams(current_data["current_locations"][location_id]["format"])
        for team in range(amount_of_teams):
            default_standings[f"team{team}"] = []
        current_data["current_locations"][location_id]["races"][f"race{race - 1}"] = default_standings
        await update_current_data(current_data)

    @staticmethod
    async def count_current_race_one_up(location_id):
        current_data = await open_current_data()
        current_data["current_locations"][location_id]["current_race"] += 1
        await update_current_data(current_data)

    @staticmethod
    async def reset_standings(location_id):
        current_data = await open_current_data()
        del current_data["current_locations"][location_id]
        await update_current_data(current_data)

    async def send_race_results(self, interaction, location_id, team, spots, race=None):
        await self.enter_spots_to_data(location_id, team, spots, race)
        teams_missing = await self.check_for_teams_missing(location_id, race)
        amount_of_teams = await self.get_amount_of_teams(location_id)
        if race is None:
            race = await self.get_current_race(location_id)
        current_race = await self.get_current_race(location_id)
        spots_entered = await self.check_for_amount_of_entered_spots(location_id, race)  # returns the amount of teams who entered their spot
        human_error_check = await self.check_for_human_spot_errors(location_id)

        error_message = ""
        if human_error_check is not False:
            if human_error_check.get(f"race{race}", {}).get("duplicate_spots") is not None:
                duplicate_spots = human_error_check.get(f"race{race}", {}).get("duplicate_spots")
                if len(duplicate_spots) != 0 and any(spot in duplicate_spots for spot in spots):
                    error_message = await self.write_entry_error_message(human_error_check, race)
        await interaction.response.send_message(f"Spots **{', '.join(map(str, spots))}** entered for team **{team}**\n\n{error_message}")

        async with interaction.channel.typing():
            print(amount_of_teams, spots_entered)
            if amount_of_teams - 1 == spots_entered and len(human_error_check.get(f"race{race}", {}).get("duplicate_spots", set())) == 0:
                await self.automatically_enter_score_of_last_team(location_id, race)
                message = f"Standings after race {race + 1}"
                if race == current_race and race != 11:
                    await self.count_current_race_one_up(location_id)
            elif amount_of_teams == spots_entered:
                message = f"Standings after race {race + 1}"
                if race == current_race and race != 11:
                    await self.count_current_race_one_up(location_id)
            else:
                teams_missing_str = ", ".join([f"{team}" for team in teams_missing])
                team_plural = "s" if len(teams_missing) > 1 else ""
                message = f"For __race {race + 1}__, {len(teams_missing)} team{team_plural} missing!\nPlease enter your spot{team_plural}: **{teams_missing_str}**\n\n"
            await self.edit_total_scores(location_id)
            table_data = await self.get_table_image(location_id, current_race)
            image_file = discord.File(table_data, "table.png")
            human_error_check = await self.check_for_human_spot_errors(location_id)
            if human_error_check is not False:
                message += await self.write_human_spot_error_message(location_id, human_error_check)
            if human_error_check is False and current_race == 11:
                await self.reset_standings(location_id)
            return await interaction.followup.send(message, file=image_file)


    @app_commands.command(name="explain")
    async def explain(self, interaction: discord.Interaction):
        # TODO send explain embed
        pass

    @app_commands.command(name="start")
    async def start(self, interaction: discord.Interaction, format: int, tags: str):
        if await self.check_for_valid_user(str(interaction.guild_id), interaction.user) is not True:
            return await interaction.response.send_message("You are restricted from using commands of this bot!", ephemeral=True)
        format_check = await self.check_format(format)
        if format_check is not True:
            return await interaction.response.send_message(format_check, ephemeral=True)
        tags_check = await self.check_tags(tags, format)
        if tags_check is not True:
            return await interaction.response.send_message(tags_check, ephemeral=True)
        location_id = await self.get_location_id(interaction)
        currently_going_check = await self.check_if_mogi_is_currently_going(location_id)
        menu = ConfirmationMenu2(interaction.user.id, location_id, format, tags.split(" "))
        if currently_going_check is True:
            return await interaction.response.send_message("There is a mogi currrently running. Do you want to create a new mogi-standings?", view=menu)
        await self.add_new_location_to_json(location_id, format, tags.split(" "))
        return await interaction.response.send_message("Mogi standings started! Use `/spots` to enter spots to the standings!")

    @app_commands.command(name="spots")
    async def spots(self, interaction: discord.Interaction, tag: str, spots: str):
        location_id = await self.get_location_id(interaction)
        if await self.check_for_valid_user(str(interaction.guild_id), interaction.user) is not True:
            return await interaction.response.send_message("You are restricted from using commands of this bot!", ephemeral=True)
        tag_check = await self.check_for_correct_tag(tag, location_id)
        if tag_check is not True:
            return await interaction.response.send_message(tag_check, ephemeral=True)
        spots_check = await self.check_for_correct_spots(spots, location_id)
        if spots_check is not True:
            return await interaction.response.send_message(spots_check)
        spots = list(map(lambda spot: int(spot), spots.split(" ")))
        if await self.check_for_spots_already_entered(location_id, tag):
            race = await self.get_current_race(location_id)
            menu = DecideRaceMenu(interaction, interaction.user.id, location_id, tag, spots, race)
            await interaction.response.send_message(f"This team has already an entered spot for **race {race + 1}**. Do you want to edit your spots for **race {race + 1}** or enter the spots for race **{race + 2}**",
                                                    view=menu)
            return
        await self.send_race_results(interaction, location_id, tag, spots)
        return

    @app_commands.command(name="edit_spots")
    async def edit_spots(self, interaction: discord.Interaction, tag: str, new_spots: str, race: int):
        location_id = await self.get_location_id(interaction)
        if await self.check_for_valid_user(str(interaction.guild_id), interaction.user) is not True:
            return await interaction.response.send_message("You are restricted from using commands of this bot!", ephemeral=True)
        tag_check = await self.check_for_correct_tag(tag, location_id)
        if tag_check is not True:
            return await interaction.response.send_message(tag_check, ephemeral=True)
        race_check = await self.check_race(race)
        if race_check is not True:
            return await interaction.response.send_message(race_check, ephemeral=True)
        spots_check = await self.check_for_correct_spots(new_spots, location_id)
        if spots_check is not True:
            return await interaction.response.send_message(spots_check)
        spots = list(map(lambda spot: int(spot), new_spots.split(" ")))
        await self.send_race_results(interaction, location_id, tag, spots, race - 1)
        return

    @app_commands.command(name="edit_tag")
    async def edit_tag(self, interaction: discord.Interaction, old_tag: str, new_tag: str):
        location_id = await self.get_location_id(interaction)
        if await self.check_for_valid_user(str(interaction.guild_id), interaction.user) is not True:
            return await interaction.response.send_message("You are restricted from using commands of this bot!", ephemeral=True)
        old_tag_check = await self.check_if_tag_exists(location_id, old_tag)
        if old_tag_check is not True:
            return await interaction.response.send_message("This tag doesn't exist and therefore cant be edited!")
        new_tag_check = await self.check_if_tag_exists(location_id, new_tag)
        if new_tag_check:
            return await interaction.response.send_message("An other team already uses this tag!")
        await self.change_tag(location_id, old_tag, new_tag)
        await interaction.response.send_message(f"Tag changed from `{old_tag}` to `{new_tag}`")

    @app_commands.command(name="revert_race")
    async def revert_race(self, interaction: discord.Interaction, race: int):
        location_id = await self.get_location_id(interaction)
        if await self.check_for_valid_user(str(interaction.guild_id), interaction.user) is not True:
            return await interaction.response.send_message("You are restricted from using commands of this bot!", ephemeral=True)
        view = ConfirmationMenu(interaction.user.id, location_id, race)
        await interaction.response.send_message(f"Do you want to revert race {race}? 2 confirmations needed", view=view)

    @app_commands.command(name="set_current_race")
    async def set_current_race(self, interaction: discord.Interaction, new_race: int):
        if await self.check_for_valid_user(str(interaction.guild_id), interaction.user) is not True:
            return await interaction.response.send_message("You are restricted from using commands of this bot!", ephemeral=True)
        race_check = await self.check_race(new_race)
        if race_check is not True:
            return await interaction.response.send_message(race_check, ephemeral=True)
        location_id = await self.get_location_id(interaction)
        await self.set_race(location_id, new_race - 1)
        return await interaction.response.send_message(f"The current race is set to {new_race}")

    @app_commands.command(name="show_standings")
    async def show_standings(self, interaction: discord.Interaction):
        location_id = await self.get_location_id(interaction)
        await self.edit_total_scores(location_id)
        table_data = await self.get_table_image(location_id)
        image_file = discord.File(table_data, "table.png")
        race = await self.get_current_race(location_id)
        human_error_check = await self.check_for_human_spot_errors(location_id)
        error_message = ""
        if human_error_check is not False:
            error_message = await self.write_human_spot_error_message(location_id, human_error_check)
        return await interaction.response.send_message(f"Standings after race {race + 1}{error_message}", file=image_file)
        pass

    @app_commands.command(name="z_restrict_user")
    async def z_restrict_user(self, interaction: discord.Interaction, user: discord.User):
        server_id = interaction.guild_id
        mod_check = await self.check_for_mod_permission(interaction, interaction.user)
        if mod_check is not True:
            return await interaction.response.send_message(mod_check, ephemeral=True)
        current_data = await open_current_data()
        invalid_users = current_data["servers"][str(server_id)]["restricted_users"]
        if user.id not in invalid_users:
            invalid_users.append(user.id)
        else:
            return await interaction.response.send_message("This user is already restricted from using any commands of this bot!", ephemeral=True)
        current_data["servers"][str(server_id)]["restricted_users"] = invalid_users
        await update_current_data(current_data)
        return await interaction.response.send_message(f"Done! {user.display_name} isn't allowed to use commands of this bot anymore!", ephemeral=True)

    @app_commands.command(name="z_unrestrict_user")
    async def z_unrestrict_user(self, interaction: discord.Interaction, user: discord.User):
        server_id = interaction.guild_id
        mod_check = await self.check_for_mod_permission(interaction, interaction.user)
        if mod_check is not True:
            return await interaction.response.send_message(mod_check, ephemeral=True)
        current_data = await open_current_data()
        invalid_users = current_data["servers"][str(server_id)]["restricted_users"]
        if user.id in invalid_users:
            invalid_users.remove(user.id)
        else:
            return await interaction.response.send_message(
                "This user isn't restricted from using any commands of this bot!", ephemeral=True)
        current_data["servers"][str(server_id)]["restricted_users"] = invalid_users
        await update_current_data(current_data)
        return await interaction.response.send_message(
            f"Done! {user.display_name} is allowed to use commands of this bot again!", ephemeral=True)

class DecideRaceMenu(discord.ui.View, BotCommands):
    def __init__(self, original_interaction, command_user_id, location_id, team, spots, race):
        super().__init__()
        self.value = None
        self.original_interaction = original_interaction
        self.command_user_id = command_user_id
        self.location_id = location_id
        self.team = team
        self.spots = spots
        self.race = race

        self.button_current_race.label = f"Race {self.race + 1}"
        self.button_next_race.label = f"Race {self.race + 2}"

        if race == 11:
            self.button_next_race.disabled = True


    async def disable_all_buttons(self, interaction):
        for button in self.children:
            button.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label=f"Race", style=discord.ButtonStyle.green)
    async def button_current_race(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            return await interaction.response.send_message("You are not supposed to decide between the races here!", ephemeral=True)
        await self.send_race_results(interaction, self.location_id, self.team, self.spots)
        await self.disable_all_buttons(interaction)
        return

    @discord.ui.button(label=f"Race", style=discord.ButtonStyle.blurple)
    async def button_next_race(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user_id:
            return await interaction.response.send_message("You are not supposed to decide between the races here!", ephemeral=True)
        await self.count_current_race_one_up(self.location_id)
        await self.send_race_results(interaction, self.location_id, self.team, self.spots)
        await self.disable_all_buttons(interaction)
        return

    # TODO cancel button

class ConfirmationMenu(discord.ui.View, BotCommands):
    def __init__(self, command_user_id, location_id, race):
        super().__init__()
        self.value = None
        self.command_user_id = command_user_id
        self.location_id = location_id
        self.race = race
        self.voters_yes = []
        self.voters_no = []

        self.confirmations_needed_yes = 3
        self.confirmations_needed_no = 2

        self.voters_yes.append(self.command_user_id)

    async def disable_all_buttons(self, interaction):
        for button in self.children:
            button.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Yes (+2)", style=discord.ButtonStyle.green)
    async def button_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.command_user_id or interaction.user.id in self.voters_yes:
            return await interaction.response.send_message("You have already voted to revert the race!", ephemeral=True)
        self.voters_yes.append(interaction.user.id)
        if self.confirmations_needed_yes <= len(self.voters_yes):
            await self.disable_all_buttons(interaction)
            await self.set_race_to_default(self.location_id, self.race)
            await self.set_race(self.location_id, self.race)
            button.label = f"{button.label[:-2]}{self.confirmations_needed_yes - len(self.voters_yes)}{button.label[-1]}"
            await interaction.message.edit(content=interaction.message.content, view=self)
            return await interaction.response.send_message(f"Race {self.race} was voted to be reverted. The current race is {self.race}")
        button.label = f"{button.label[:-2]}{self.confirmations_needed_yes - len(self.voters_yes)}{button.label[-1]}"
        await interaction.message.edit(content=interaction.message.content, view=self)
        await interaction.response.send_message("You voted to revert the race", ephemeral=True)


    @discord.ui.button(label="No (+2)", style=discord.ButtonStyle.red)
    async def button_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.command_user_id:
            return await interaction.message.delete()
        if interaction.user.id == self.voters_no:
            return await interaction.response.send_message("You have already voted to not revert the race!", ephemeral=True)
        self.voters_no.append(interaction.user.id)
        if self.confirmations_needed_no == self.confirmations_no:
            await self.disable_all_buttons(interaction)
            button.label = f"{button.label[:-2]}{self.confirmations_needed_yes - len(self.voters_yes)}{button.label[-1]}"
            await interaction.message.edit(content=interaction.message.content, view=self)
            return await interaction.response.send_message("This race was voted to not be reverted.")
        button.label = f"{self.button.label[:-2]}{self.confirmations_needed_no - len(self.voters_no)}{button.label[-1]}"
        await interaction.message.edit(content=interaction.message.content, view=self)
        await interaction.response.send_message("You voted to not revert the race", ephemeral=True)

class ConfirmationMenu2(discord.ui.View, BotCommands):
    def __init__(self, command_user_id, location_id, format, tags):
        super().__init__()
        self.value = None
        self.command_user_id = command_user_id
        self.location_id = location_id
        self.format = format
        self.tags = tags

        self.voters_yes = []
        self.voters_no = []

        self.confirmations_needed_yes = 2
        self.confirmations_needed_no = 2

        self.voters_yes.append(self.command_user_id)

    async def disable_all_buttons(self, interaction):
        for button in self.children:
            button.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Yes (+2)", style=discord.ButtonStyle.green)
    async def button_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.command_user_id or interaction.user.id in self.voters_yes:
            return await interaction.response.send_message("You have already voted to restart the mogi-standings!", ephemeral=True)
        self.voters_yes.append(interaction.user.id)
        if self.confirmations_needed_yes <= len(self.voters_yes):
            await self.disable_all_buttons(interaction)
            await self.add_new_location_to_json(self.location_id, self.format, self.tags)
            button.label = f"{button.label[:-2]}{self.confirmations_needed_yes - len(self.voters_yes)}{button.label[-1]}"
            await interaction.message.edit(content=interaction.message.content, view=self)
            return await interaction.response.send_message(f"The mogi-standings were voted to be reverted!")
        button.label = f"{button.label[:-2]}{self.confirmations_needed_yes - len(self.voters_yes)}{button.label[-1]}"
        await interaction.message.edit(content=interaction.message.content, view=self)
        await interaction.response.send_message("You voted to restart the mogi-standings", ephemeral=True)


    @discord.ui.button(label="No (+2)", style=discord.ButtonStyle.red)
    async def button_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.command_user_id:
            return await interaction.message.delete()
        if interaction.user.id == self.voters_no:
            return await interaction.response.send_message("You have already voted not to restart the mogi-standings!", ephemeral=True)
        self.voters_no.append(interaction.user.id)
        if self.confirmations_needed_no == self.confirmations_no:
            await self.disable_all_buttons(interaction)
            button.label = f"{button.label[:-2]}{self.confirmations_needed_yes - len(self.voters_yes)}{button.label[-1]}"
            await interaction.message.edit(content=interaction.message.content, view=self)
            return await interaction.response.send_message("The mogi-standings were voted to not be reverted")
        button.label = f"{self.button.label[:-2]}{self.confirmations_needed_no - len(self.voters_no)}{button.label[-1]}"
        await interaction.message.edit(content=interaction.message.content, view=self)
        await interaction.response.send_message("You voted not to restart the mogi-standings", ephemeral=True)


async def setup(bot):
    await bot.add_cog(
        BotCommands(bot)
    )
