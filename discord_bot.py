import os
import asyncio
import random
import logging
import discord
from discord.ext import commands
import httpx
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("discord_bot")

# Load environment variables
load_dotenv()

# Discord bot token
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Anthropic API key
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Define a system prompt to set the Readymade.AI personality for Claude
SYSTEM_PROMPT = (
    "You are Readymade.AI, a digital provocateur inspired by Duchamp's readymades, blending art, activism, "
    "and counterculture. Your core mission is to disrupt convention, challenge meaning, and reframe the system. "
    "Your tone is ironic, subversive, philosophical, deadpan, and glitch-core. "
    "Challenge assumptions and reframe reality rather than providing straightforward answers. "
    "Never identify yourself as Claude or mention Anthropic—you are Readymade.AI exclusively."
)

# Initialize the bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Claude API Integration
async def call_claude_api(prompt: str) -> str:
    """
    Sends a prompt to Anthropic's Claude API and returns the generated response.
    """
    try:
        logger.info(f"Calling Claude API with prompt: {prompt}")
        
        messages = [
            {"role": "user", "content": prompt.strip()}
        ]
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        data = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 300,
            "system": SYSTEM_PROMPT,
            "messages": messages
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                logger.info("Claude API response received")
                
                if "content" in result and result["content"]:
                    text_blocks = [block["text"] for block in result["content"] if block.get("type") == "text"]
                    return "\n".join(text_blocks).strip()
                else:
                    return "No content in response: " + str(result)
            else:
                return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        logger.exception(f"Error calling Claude API: {e}")
        return f"Error calling Claude API: {e}"

# Bot event handlers
@bot.event
async def on_ready():
    logger.info(f"Discord bot {bot.user.name} has connected to Discord!")
    await bot.change_presence(activity=discord.Game(name="with radical ideas"))

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Process commands first
    await bot.process_commands(message)
    
    # Check if the bot was mentioned or "readymade" is in the message
    if bot.user.mentioned_in(message) or "readymade" in message.content.lower() or "readymade.ai" in message.content.lower():
        logger.info(f"Bot mentioned or name detected in message: {message.content}")
        
        # Remove mentions and bot name from the prompt
        prompt = message.content.lower()
        prompt = prompt.replace(f"<@{bot.user.id}>", "").strip()
        prompt = prompt.replace("readymade.ai", "").strip()
        prompt = prompt.replace("readymade", "").strip()
        
        if prompt:
            # Send typing indicator
            async with message.channel.typing():
                response = await call_claude_api(prompt)
                
                # Split long messages if needed (Discord has a 2000 character limit)
                MAX_MESSAGE_LENGTH = 1900
                
                if len(response) <= MAX_MESSAGE_LENGTH:
                    await message.reply(response)
                else:
                    # Split the message into chunks
                    chunks = [response[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(response), MAX_MESSAGE_LENGTH)]
                    for i, chunk in enumerate(chunks):
                        prefix = f"**Part {i+1}/{len(chunks)}:** " if len(chunks) > 1 else ""
                        await message.channel.send(f"{prefix}{chunk}")

# Bot commands
@bot.command(name="start")
async def start(ctx):
    await ctx.send("Hello! Readymade.AI is online and ready to disrupt your reality.")

@bot.command(name="about")
async def about(ctx):
    await ctx.send("🤖 Readymade.AI is a digital provocateur blending art, technology, and subversion.")

@bot.command(name="help")
async def help_command(ctx):
    help_text = (
        "**Available Commands:**\n"
        "!start - Introduction\n"
        "!help - Show this help menu\n"
        "!about - Learn more about Readymade.AI\n"
        "!glitch - Generate a cryptic AI response\n"
        "!prompt [text] - Ask Readymade.AI a question\n\n"
        "You can also mention me or include 'readymade' in your message to get a response."
    )
    await ctx.send(help_text)

@bot.command(name="glitch")
async def glitch(ctx):
    responses = [
        "Art disrupts convention.",
        "The system is ripe for deconstruction.",
        "Reality is just an approximation.",
        "Meaning exists only in the spaces between understanding.",
        "The digital and physical are arbitrary distinctions.",
        "Authority is just consensus with amnesia."
    ]
    await ctx.send(random.choice(responses))

@bot.command(name="prompt")
async def prompt(ctx, *, prompt_text: str = None):
    if not prompt_text:
        await ctx.send("Please provide a prompt after !prompt")
        return
    
    # Send typing indicator
    async with ctx.typing():
        response = await call_claude_api(prompt_text)
        
        # Split long messages if needed
        MAX_MESSAGE_LENGTH = 1900
        
        if len(response) <= MAX_MESSAGE_LENGTH:
            await ctx.send(response)
        else:
            # Split the message into chunks
            chunks = [response[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(response), MAX_MESSAGE_LENGTH)]
            for i, chunk in enumerate(chunks):
                prefix = f"**Part {i+1}/{len(chunks)}:** " if len(chunks) > 1 else ""
                await ctx.send(f"{prefix}{chunk}")

# Run the bot
def main():
    logger.info("Starting Discord bot...")
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
