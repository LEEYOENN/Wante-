import discord
from discord.ext import commands
from dotenv import load_dotenv
import os 

load_dotenv()

DISCORD_CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if __name__ == "__main__":

    # print("토큰:", DISCORD_BOT_TOKEN)
    # print("채널 ID:", DISCORD_CHANNEL_ID)
    if not DISCORD_CHANNEL_ID or not DISCORD_CHANNEL_ID.isdigit():
        print("환경변수 'DISCORD_CHANNEL_ID'를 확인하세요.")
    intents = discord.Intents.default() # 디스코드 봇이 서버와 상호작용 할 때 어떤 종류의 이벤트를 받아올지를 설정
    intents.message_content = True # 메시지 내용 접근
    intents.members = True # 멤버 접근(필요 시)

    bot = commands.Bot(command_prefix='!', intents=intents)

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user}.")

        channel = bot.get_channel(int(DISCORD_CHANNEL_ID))
        if channel is None:
            print("채널이 없습니다. 😢")
            return
        print("채널이 연결되었습니다. 😊")

        # --- 알림(메시지)를 보내는 코드 추가 ---
        try:
            # channel.send() 함수를 사용하여 메시지를 비동기적으로 전송
            await channel.send("봇이 성공적으로 시작되었습니다!")
            print("알림 메시지 전송 완료!")
        except discord.Forbidden:
            print("메시지 전송 권한이 없습니다. (봇의 권한을 확인하세요.)")
        except Exception as e:
            print("메시지 전송 중 오류 발생: {e}")
    
    @bot.command()
    async def 안녕(ctx):
        """ 사용자에게 인사를 건넵니다. """
        await ctx.send(f"{ctx.author.display_name}님 안녕하세요! 만나서 반갑습니다. 👋")
        # -----------------------------------
    bot.run(str(DISCORD_BOT_TOKEN))