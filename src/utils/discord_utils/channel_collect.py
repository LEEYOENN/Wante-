import discord
import os
import asyncio
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_SERVER_ID = os.getenv("DISCORD_SERVER_ID")

intents = discord.Intents.default()

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
    print("이 서버의 모든 채널 목록:")

    all_channels_data = []

    # 5. 해당 서버의 guild.channels 속성을 순회
    for channel in guild.channels:
        channel_data = {
            "channel_id": str(channel.id),
            "channel_name": channel.name,
            "channel_type": str(channel.type)
        }
    
        all_channels_data.append(channel_data)

        print(f"채널 ID: {channel.id:<20} | 채널 이름: {channel.name:<20} | 채널 타입: {channel.type}")
    print(f"\n총 수집된 채널 수: {len(all_channels_data)}")

    df = pd.DataFrame(all_channels_data)
    df.to_csv(r"C:\Users\user\potenup\Wante\data\discord_server_channel.csv", index=False)

    # 봇이 할일이 끝났으면 close
    await client.close()

if __name__ == "__main__":
    client.run(str(DISCORD_BOT_TOKEN))