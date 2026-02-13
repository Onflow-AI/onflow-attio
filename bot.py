"""
Discord Lead Bot - Main Entry Point

AI-powered Discord bot that extracts lead information from natural language,
enriches with LinkedIn data, and creates leads in Attio CRM.
"""

import logging
import sys
import asyncio

import discord
from discord.ext import commands

from config import Config
from gemini_processor import process_lead_message, GeminiProcessingError
from attio_client import create_record, AttioAPIError

logger = logging.getLogger(__name__)


class LeadBot(commands.Bot):
    """Discord bot for intelligent lead extraction and CRM integration."""

    def __init__(self):
        """Initialize the bot with required intents."""
        intents = discord.Intents.default()
        intents.message_content = True  # Required to read message content
        intents.guilds = True
        intents.guild_messages = True

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None  # Disable default help command
        )

    async def on_ready(self):
        """Called when the bot is ready and connected to Discord."""
        logger.info(f"Bot connected as {self.user.name} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        print("\n" + "=" * 70)
        print(f"✅ {self.user.name} is online and ready!")
        print("=" * 70)
        print(f"\nConnected to {len(self.guilds)} server(s)")
        print("\nMention me with any of these:")
        print("  • Person: 'I met Sarah Johnson, VP at Acme'")
        print("  • Company: 'Working with Acme Corp'")
        print("  • Deal: '$50k deal with TechCo'")
        print("  • User: 'Hired John Smith as engineer'")
        print("\nI'll automatically detect the type and create it in Attio!\n")

    async def on_message(self, message: discord.Message):
        """
        Handle incoming messages and process lead extraction.

        Args:
            message: Discord message object
        """
        # Ignore messages from the bot itself
        if message.author == self.user:
            return

        # Process commands first
        await self.process_commands(message)

        # Check if bot is mentioned
        if self.user.mentioned_in(message):
            await self.handle_lead_mention(message)

    async def handle_lead_mention(self, message: discord.Message):
        """
        Handle a message where the bot is mentioned.

        This is the main workflow:
        1. Extract message content (remove bot mention)
        2. Send to Claude for processing
        3. Enrich with LinkedIn data
        4. Create lead in Attio
        5. Send confirmation

        Args:
            message: Discord message where bot was mentioned
        """
        try:
            # Send "thinking" indicator
            async with message.channel.typing():
                # Extract message content (remove bot mention)
                content = message.content
                for mention in message.mentions:
                    content = content.replace(f"<@{mention.id}>", "").strip()
                    content = content.replace(f"<@!{mention.id}>", "").strip()

                if not content:
                    await message.reply("Please provide information! Example: @bot Met Sarah Chen, VP at Stripe")
                    return

                logger.info(f"Processing from {message.author}: {content}")

                # Step 1: Extract data with Gemini (includes object_type detection)
                await message.add_reaction("🤖")  # Bot is processing
                lead_data = await process_lead_message(content)

                # Step 2: Create record in Attio
                await message.add_reaction("💾")  # Saving to CRM
                created_record = await create_record(lead_data)

                # Step 3: Send confirmation
                try:
                    await message.clear_reactions()
                except discord.Forbidden:
                    pass  # Bot doesn't have Manage Messages permission
                await message.add_reaction("✅")  # Success!

                # Build response message
                response = self._build_success_message(lead_data, created_record)
                await message.reply(response)

                logger.info(f"Successfully created {lead_data.object_type}: {lead_data.name}")

        except GeminiProcessingError as e:
            logger.error(f"Gemini processing error: {e}")
            try:
                await message.clear_reactions()
            except discord.Forbidden:
                pass  # Bot doesn't have Manage Messages permission
            await message.add_reaction("❌")
            await message.reply(
                f"❌ Failed to extract information.\n"
                f"Error: {str(e)}\n\n"
                f"Please try rephrasing your message."
            )

        except AttioAPIError as e:
            logger.error(f"Attio API error: {e}")
            try:
                await message.clear_reactions()
            except discord.Forbidden:
                pass  # Bot doesn't have Manage Messages permission
            await message.add_reaction("⚠️")
            await message.reply(
                f"⚠️ Information extracted but failed to save to Attio.\n"
                f"Error: {str(e)}\n\n"
                f"Extracted data:\n"
                f"• Type: {lead_data.object_type}\n"
                f"• Name: {lead_data.name}\n"
                f"• Company: {lead_data.company or 'N/A'}"
            )

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            try:
                await message.clear_reactions()
            except discord.Forbidden:
                pass  # Bot doesn't have Manage Messages permission
            await message.add_reaction("❌")
            await message.reply(
                f"❌ An unexpected error occurred: {str(e)}\n\n"
                f"Please try again or contact support."
            )

    def _build_success_message(self, lead_data, created_record) -> str:
        """
        Build a formatted success message.

        Args:
            lead_data: Extracted lead data from Gemini
            created_record: Created Attio record

        Returns:
            Formatted message string
        """
        # Emoji for object type
        emoji_map = {
            "person": "👤",
            "company": "🏢",
            "deal": "💰",
            "user": "👥"
        }
        emoji = emoji_map.get(lead_data.object_type, "✅")

        lines = [
            f"{emoji} **{lead_data.object_type.capitalize()} Created Successfully!**",
            "",
            f"**Name:** {lead_data.name}",
        ]

        # Add fields based on object type
        if lead_data.object_type in ["person", "user"]:
            if lead_data.company:
                lines.append(f"**Company:** {lead_data.company}")

            if lead_data.job_title:
                lines.append(f"**Title:** {lead_data.job_title}")

            if lead_data.email:
                lines.append(f"**Email:** {lead_data.email}")

            if lead_data.phone:
                lines.append(f"**Phone:** {lead_data.phone}")

            if lead_data.location:
                lines.append(f"**Location:** {lead_data.location}")

            if lead_data.linkedin_url:
                lines.append(f"**LinkedIn:** {lead_data.linkedin_url}")

        elif lead_data.object_type == "company":
            if lead_data.location:
                lines.append(f"**Location:** {lead_data.location}")

        elif lead_data.object_type == "deal":
            if lead_data.company:
                lines.append(f"**Company:** {lead_data.company}")

            if lead_data.deal_value:
                lines.append(f"**Value:** ${lead_data.deal_value:,.0f}")

            if lead_data.deal_stage:
                lines.append(f"**Stage:** {lead_data.deal_stage}")

        if lead_data.notes:
            lines.append(f"**Notes:** {lead_data.notes}")

        return "\n".join(lines)


# Command: Help
@commands.command(name='help')
async def help_command(ctx):
    """Display help information."""
    help_text = """
    **Discord Attio Bot - Help**

    **Usage:**
    Mention me with information and I'll automatically detect the type and create it in Attio!

    **Supported Types:**
    👤 **Person** - Individual contacts
    🏢 **Company** - Organizations
    💰 **Deal** - Sales opportunities
    👥 **User** - Team members

    **Examples:**
    • `@bot I met Sarah Johnson, VP of Sales at Acme Corp` → Creates Person
    • `@bot Working with Acme Corp, SaaS company in SF` → Creates Company
    • `@bot $50k deal with TechCo for enterprise plan` → Creates Deal
    • `@bot Hired John Smith as senior engineer` → Creates User

    **What I do:**
    1. Analyze your message and detect object type
    2. Extract relevant information (including LinkedIn URLs if provided)
    3. Create record in Attio CRM

    **Commands:**
    • `!help` - Show this help message
    • `!status` - Check bot status
    """
    await ctx.reply(help_text)


# Command: Status
@commands.command(name='status')
async def status_command(ctx):
    """Check bot and API status."""
    status_lines = ["**Bot Status Check**\n"]

    # Check Discord connection
    status_lines.append("✅ Discord: Connected")

    # Check Google AI Studio configuration
    if Config.GOOGLE_API_KEY:
        status_lines.append("✅ Google Gemini API: Configured")
    else:
        status_lines.append("❌ Google Gemini API: Not configured")

    # Check Attio configuration
    if Config.ATTIO_API_KEY:
        status_lines.append("✅ Attio: Configured")
    else:
        status_lines.append("❌ Attio: Not configured")

    await ctx.reply("\n".join(status_lines))


async def main():
    """Main entry point for the bot."""
    print("\n" + "=" * 70)
    print("DISCORD LEAD BOT - Starting Up")
    print("=" * 70)

    # Validate configuration
    if not Config.validate():
        print("\n❌ Configuration validation failed!")
        print("Please check your .env file and ensure all required variables are set.")
        print("See .env.example for required variables.\n")
        sys.exit(1)

    # Create and run bot
    print("\nStarting Discord bot...")
    bot = LeadBot()

    # Add commands
    bot.add_command(help_command)
    bot.add_command(status_command)

    try:
        await bot.start(Config.DISCORD_BOT_TOKEN)
    except discord.LoginFailure:
        print("\n❌ Failed to login to Discord!")
        print("Please check your DISCORD_BOT_TOKEN in .env file.\n")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
        await bot.close()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logger.error("Fatal error", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nBot stopped by user.")
