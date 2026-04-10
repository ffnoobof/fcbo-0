import os
import random
import re
from typing import Dict, List

import discord
from discord import app_commands
from discord.ext import commands

# Global in-memory team storage.
# Structure:
# [
#   {
#     "team_name": "string",
#     "members": ["user_id1", "user_id2"]
#   }
# ]
teams: List[Dict[str, List[str]]] = []


class TournamentBot(commands.Bot):
    """Discord bot with slash commands for managing tournament teams and groups."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        """Sync slash commands globally when the bot starts."""
        await self.tree.sync()


bot = TournamentBot()


def parse_member_ids(members_input: str) -> List[str]:
    """
    Parse a string containing Discord mentions and extract unique user IDs in order.

    Supports mention formats:
    - <@123456789>
    - <@!123456789>
    """
    matches = re.findall(r"<@!?(\d+)>", members_input)

    unique_ids: List[str] = []
    seen = set()
    for user_id in matches:
        if user_id not in seen:
            seen.add(user_id)
            unique_ids.append(user_id)
    return unique_ids


def build_teams_embed(title: str, description: str) -> discord.Embed:
    """Create a consistently-styled gold embed."""
    return discord.Embed(title=title, description=description, color=discord.Color.gold())


@bot.tree.command(name="addteam", description="Add a team with members using mentions.")
@app_commands.describe(
    team_name="Unique team name",
    members="Members as mentions, e.g. @User1 @User2",
)
async def addteam(interaction: discord.Interaction, team_name: str, members: str) -> None:
    """Add a team to in-memory storage after validating input."""
    clean_name = team_name.strip()
    member_ids = parse_member_ids(members)

    if not clean_name:
        embed = build_teams_embed("❌ Invalid Team Name", "Team name cannot be empty.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not member_ids:
        embed = build_teams_embed(
            "❌ Invalid Members",
            "No valid mentions were found. Please mention users like: @User1 @User2",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Optional safeguard: prevent duplicate team names (case-insensitive).
    if any(team["team_name"].lower() == clean_name.lower() for team in teams):
        embed = build_teams_embed(
            "❌ Duplicate Team",
            f"A team named **{clean_name}** already exists.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    teams.append({"team_name": clean_name, "members": member_ids})

    mentions = " ".join(f"<@{user_id}>" for user_id in member_ids)
    embed = build_teams_embed("✅ Team Added", f"**{clean_name}**: {mentions}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="showteams", description="Show all currently stored teams.")
async def showteams(interaction: discord.Interaction) -> None:
    """Display all saved teams and member mentions."""
    if not teams:
        embed = build_teams_embed("📋 Teams", "No teams are currently stored.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    lines = []
    for idx, team in enumerate(teams, start=1):
        mentions = " ".join(f"<@{user_id}>" for user_id in team["members"])
        lines.append(f"**{idx}. {team['team_name']}**: {mentions}")

    embed = build_teams_embed("📋 Stored Teams", "\n".join(lines))
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="clearteams", description="Remove all stored teams.")
async def clearteams(interaction: discord.Interaction) -> None:
    """Clear the global in-memory teams list."""
    teams.clear()
    embed = build_teams_embed("🧹 Teams Cleared", "All teams have been removed.")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="cedex", description="Shuffle teams and split them into tournament groups.")
@app_commands.describe(group_count="Number of groups to generate")
async def cedex(interaction: discord.Interaction, group_count: int) -> None:
    """Generate tournament groups using random shuffle and round-robin distribution."""
    if not teams:
        embed = build_teams_embed("❌ No Teams", "No teams are stored. Add teams first with `/addteam`.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if group_count <= 0:
        embed = build_teams_embed("❌ Invalid Group Count", "`group_count` must be greater than 0.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if group_count > len(teams):
        embed = build_teams_embed(
            "❌ Too Many Groups",
            f"You requested **{group_count}** groups but only **{len(teams)}** teams exist.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    shuffled_teams = teams.copy()
    random.shuffle(shuffled_teams)

    # Round-robin distribution per requirement: groups[i % group_count]
    groups: List[List[Dict[str, List[str]]]] = [[] for _ in range(group_count)]
    for i, team in enumerate(shuffled_teams):
        groups[i % group_count].append(team)

    group_labels = [chr(ord("A") + i) for i in range(group_count)]
    sections = []
    for idx, group in enumerate(groups):
        label = group_labels[idx] if idx < 26 else str(idx + 1)
        team_lines = []
        for team in group:
            mentions = " ".join(f"<@{user_id}>" for user_id in team["members"])
            team_lines.append(f"{team['team_name']}: {mentions}")
        body = "\n".join(team_lines) if team_lines else "(No teams)"
        sections.append(f"📢 **Group {label}**\n{body}")

    embed = build_teams_embed("🏆 TOURNAMENT GROUPS 🏆", "\n\n".join(sections))
    await interaction.response.send_message(embed=embed)


def main() -> None:
    """Entrypoint for launching the Discord bot process."""
    token = os.getenv("TOKEN")
    if not token:
        # Do not raise an exception; provide a clear action message and exit cleanly.
        print("[ERROR] TOKEN environment variable is not set. Set TOKEN before running the bot.")
        return

    bot.run(token)


if __name__ == "__main__":
    main()
