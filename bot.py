import discord
import math
from discord.ext import commands
import mysql.connector
import uuid
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# .env needed
TOKEN = ''

# .env needed
DATABASE_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'DiscordBotData'
}

cursor = None

intents = discord.Intents.default()
intents.members = True  
intents.message_content = True
intents.guilds = True  

k = 10
def calculate_level(total_messages):
    return math.floor(math.sqrt(total_messages / k))
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    global conn

    conn = mysql.connector.connect(**DATABASE_CONFIG)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_birthday_reminders, 'cron', hour=7, minute=0)  
    scheduler.start()
    print(f'Bot is ready and connected to the database as {bot.user}')

@bot.event
async def on_disconnect():

    if conn.is_connected():
        conn.close()
        print("Database connection closed.")

@bot.command()
@commands.has_permissions(administrator=True)
async def set_birthday_channel(ctx, channel: discord.TextChannel):
    """Set the channel where birthday reminders will be sent."""
    cursor = conn.cursor()

    # Update the birthday reminder channel for the server
    update_query = "UPDATE servers SET birthday_reminder_channel = %s WHERE id = %s"
    cursor.execute(update_query, (channel.id, ctx.guild.id))
    conn.commit()

    cursor.close()

    await ctx.send(f"Birthday reminder channel has been set to {channel.mention}.")

def get_birthday_users(cursor, today):
    """Retrieve all users who have their birthday today, along with their server and reminder channel."""
    query = """
    SELECT members.username, servers.birthday_reminder_channel, members.server_id
    FROM members
    JOIN servers ON members.server_id = servers.id
    WHERE DATE_FORMAT(members.birthday, '%m-%d') = %s AND servers.birthday_reminder_channel IS NOT NULL
    """
    cursor.execute(query, (today,))
    return cursor.fetchall()

async def send_birthday_reminders():
    """Send birthday reminders in the appropriate channels."""
    print("Checking for birthdays...")
    cursor = conn.cursor()
    today = datetime.now().strftime('%m-%d')
    birthday_users = get_birthday_users(cursor, today)

    for username, channel_id, server_id in birthday_users:
        if channel_id:  # Only send if a channel is set
            guild = bot.get_guild(int(server_id))
            if guild:
                channel = guild.get_channel(int(channel_id))
                if channel:
                    await channel.send(f"🎉 Happy Birthday, {username}! 🎉")
                else:
                    print(f"Channel {channel_id} not found in server {guild.name} for birthday reminder.")

    cursor.close()

@bot.command()
async def set_birthday(ctx, date: str):
    """Set your birthday using the format YYYY-MM-DD."""
    try:
        # Parse the date provided by the user
        birthday = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        # Inform the user if the date format is incorrect
        await ctx.send("Invalid date format! Please use YYYY-MM-DD.")
        return

    cursor = conn.cursor()

    # Update the member's birthday in the database
    update_query = "UPDATE members SET birthday = %s WHERE id = %s"
    cursor.execute(update_query, (birthday, ctx.author.id))
    conn.commit()

    cursor.close()

    # Confirm the birthday has been set
    await ctx.send(f"{ctx.author.mention}, your birthday has been set to {birthday}.")

# Roles command
@bot.command()
async def roles(ctx, give_remove: str, role: discord.Role, user: str):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You do not have the necessary permissions to use this command.")
        return
    
    if give_remove.lower() not in ["give", "remove"]:
        await ctx.send("Invalid action! Please use 'give' to assign a role or 'remove' to remove a role.")
        return

    if user.lower() == "all":
        for member in ctx.guild.members:
            if give_remove.lower() == "give" and role not in member.roles:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    await ctx.send(f"Failed to give role to {member.mention}. Insufficient permissions.")
            elif give_remove.lower() == "remove" and role in member.roles:
                try:
                    await member.remove_roles(role)
                except discord.Forbidden:
                    await ctx.send(f"Failed to remove role from {member.mention}. Insufficient permissions.")
    else:
        member = discord.utils.get(ctx.guild.members, mention=user)
        if not member:
            await ctx.send("User not found!")
            return

        if give_remove.lower() == "give" and role not in member.roles:
            await member.add_roles(role)
            await ctx.send(f"Role '{role.name}' has been given to {member.mention}.")
        elif give_remove.lower() == "remove" and role in member.roles:
            await member.remove_roles(role)
            await ctx.send(f"Role '{role.name}' has been removed from {member.mention}.")
        else:
            await ctx.send("Invalid action or user already has/doesn't have the role.")

@bot.command()
async def level(ctx, user: discord.Member = None):
    user = user or ctx.author

    cursor = conn.cursor()

    query = "SELECT level, messages_send FROM members WHERE id = %s"
    cursor.execute(query, (user.id,))
    result = cursor.fetchone()

    if result:
        current_level, total_messages = result
        await ctx.send(f"{user.mention} is currently at level {current_level} with {total_messages} messages sent.")
    else:
        await ctx.send(f"{user.mention} has not sent any messages yet.")

    cursor.close()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    cursor = conn.cursor()

    # Check if the server exists
    server_query = "SELECT id FROM servers WHERE id = %s"
    cursor.execute(server_query, (message.guild.id,))
    server_result = cursor.fetchone()

    if not server_result:
        # Insert server if it does not exist
        insert_server_query = "INSERT INTO servers (id, server_name) VALUES (%s, %s)"
        cursor.execute(insert_server_query, (message.guild.id, message.guild.name))
        conn.commit()

    # Check if the member exists
    query = "SELECT messages_send, level FROM members WHERE id = %s"
    cursor.execute(query, (message.author.id,))
    result = cursor.fetchone()

    if result:
        # User exists, increment messages_send
        new_count = result[0] + 1
        current_level = result[1]
        update_query = "UPDATE members SET messages_send = %s WHERE id = %s"
        cursor.execute(update_query, (new_count, message.author.id))
    else:
        # User does not exist, insert a new record
        new_count = 1
        current_level = 0  # New user starts at level 0
        insert_query = """
        INSERT INTO members (id, server_id, username, messages_send, level)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (
            message.author.id,
            message.guild.id,
            str(message.author),
            new_count,
            current_level
        ))


    new_level = calculate_level(new_count)

    # Check if the user leveled up
    if new_level > current_level:
        update_level_query = "UPDATE members SET level = %s WHERE id = %s"
        cursor.execute(update_level_query, (new_level, message.author.id))
        conn.commit()
        await message.channel.send(f"Congratulations {message.author.mention}, you've leveled up to level {new_level}!")


    conn.commit()

    cursor.close()


    await bot.process_commands(message)

@bot.command(name='create_ticket')
async def create_ticket(ctx, *, issue_description):
    cursor = conn.cursor()
    server_id = str(ctx.guild.id)
    user_id = str(ctx.author.id)
    ticket_id = str(uuid.uuid4())

    # Insert server into the database if not exists
    cursor.execute("INSERT IGNORE INTO servers (id, server_name) VALUES (%s, %s)",
                   (server_id, ctx.guild.name))

    # Insert member into the database if not exists
    cursor.execute("INSERT IGNORE INTO members (id, server_id, username) VALUES (%s, %s, %s)",
                   (user_id, server_id, ctx.author.name))

    # Insert the support ticket into the database
    cursor.execute("""
        INSERT INTO support_tickets (id, server_id, user_id, issue_description, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (ticket_id, server_id, user_id, issue_description, 'open', datetime.now()))


    conn.commit()

    # Create a new channel for the ticket
    channel = await ctx.guild.create_text_channel(f'ticket-{ticket_id[:8]}')
    
    # Save the channel in the database
    cursor.execute("""
        INSERT INTO support_channels (id, support_ticket_id, channel_id, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (str(uuid.uuid4()), ticket_id, str(channel.id), True, datetime.now()))

    conn.commit()

    await channel.send(f'Ticket created by {ctx.author.mention}.\n\n**Issue:** {issue_description}')
    await ctx.send(f'Ticket created: {channel.mention}')
    cursor.close()


@bot.command(name='close')
async def close_ticket(ctx):
    cursor = conn.cursor()
    channel_id = str(ctx.channel.id)

    # Get the ticket ID and user ID associated with the current channel
    cursor.execute("""
        SELECT support_ticket_id, user_id FROM support_channels
        JOIN support_tickets ON support_channels.support_ticket_id = support_tickets.id
        WHERE channel_id = %s
    """, (channel_id,))
    result = cursor.fetchone()

    if result:
        ticket_id, ticket_creator_id = result

        # Check if the user is the ticket creator or an admin
        if ctx.author.id == int(ticket_creator_id) or ctx.author.guild_permissions.administrator:
            # Update the ticket status to 'closed'
            cursor.execute("""
                UPDATE support_tickets SET status = %s, resolved_at = %s WHERE id = %s
            """, ('closed', datetime.now(), ticket_id))

            # Mark the support channel as inactive
            cursor.execute("""
                UPDATE support_channels SET is_active = %s WHERE channel_id = %s
            """, (False, channel_id))


            conn.commit()

            await ctx.send(f'Ticket {ticket_id} has been closed by {ctx.author.mention}.')
            await ctx.channel.delete()
        else:
            await ctx.send('You do not have permission to close this ticket.')
    else:
        await ctx.send('This command can only be used in a ticket channel.')

    cursor.close()



bot.run(TOKEN)
