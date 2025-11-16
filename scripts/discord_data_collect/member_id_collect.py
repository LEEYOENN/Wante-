import discord
import os
import asyncio
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_SERVER_ID = os.getenv("DISCORD_SERVER_ID")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Successfully Logged in as {client.user}")
    await client.wait_until_ready()

    guild = client.get_guild(int(DISCORD_SERVER_ID))

    # 서버를 찾았는지 확인
    if guild is None:
        print("Error: 해당 서버를 찾을 수 없습니다.")
        await client.close()
        return
    
    print(f"타켓 서버: {guild.name}, ID: {guild.id}")

    specific_members_data = []

    # 5. 해당 서버의 멤버를 순회합니다.
    async for member in guild.fetch_members(limit=None):
        member_data = {
            "user_id": str(member.id),
            "user_name": member.name,
            "server_name": member.display_name,
        }

        specific_members_data.append(member_data)

        print(f"ID: {member.id:<20} | 유저 이름: {member.name:<20} | 서버 닉네임: {member.display_name}")
    print(f"\n총 수집된 멤버 수: {len(specific_members_data)}")

    df = pd.DataFrame(specific_members_data)
    df.to_csv(r"C:\Users\user\potenup\Wante\data\discord_server_member.csv", index=False)



    # 봇이 할일이 끝났으면 close
    await client.close()

if __name__ == "__main__":
    client.run(str(DISCORD_BOT_TOKEN))