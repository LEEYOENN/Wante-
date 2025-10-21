import discord
from discord.ext import commands
from dotenv import load_dotenv
import os 

load_dotenv()

USER_ID_TO_DM = 1108003654344134686
 
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if __name__ == "__main__":
    intents = discord.Intents.default() # 디스코드 봇이 서버와 상호작용 할 때 어떤 종류의 이벤트를 받아올지를 설정
    intents.message_content = True # 메시지 내용 접근
    intents.members = True # 멤버 접근(필요 시)

    bot = commands.Bot(command_prefix='!', intents=intents)
    
    @bot.event
    async def on_ready():
        """ 봇이 실행되었을 때 딱 한 번만 실행되는 이벤트입니다."""
        print(f"Logged in as {bot.user}.")

        # 코드상에서 사용자에게 DM 전송하기
        # fetch_user() 를 사용하여 사용자 ID로부터 사용자 객체를 가져옵니다.
        try:
            user = await bot.fetch_user(USER_ID_TO_DM)

            # 사용자 객체의 send() 함수를 호출하여 DM을 보냄
            await user.send(f"안녕하세요! {user.name}님 바보!\n인사를 하고싶다면 '!안녕', 통신 종료를 하고싶다면 '!종료'를 입력해수세요.")
            print(f"성공적으로 {user.name}님에게 DM을 보냈습니다.")
        
        except discord.NotFound:
            # 존재하지 않는 사용자 일 경우
            print(f"'{user.name}'사용자를 찾을 수 없습니다.")
        
        except discord.Forbidden:
            # 봇이 DM을 보낼 수 없는 경우 (상대방이 DM을 차단했거나, 서버 멤버가 아닐 때 등)
            print(f"'{user.name}' 해당 사용자에게 DM을 보낼 수 없습니다. (DM이 차단되었을 수 있습니다)")
        except Exception as e:
            print(f"DM 전송 중 오류 발생: {e}")

    @bot.command()
    async def 안녕(ctx):
        """ 사용자에게 인사를 건넵니다. """
        await ctx.send(f"{ctx.author.display_name}님 안녕하세요! 만나서 반갑습니다. 👋")

    @bot.command()
    async def 종료(ctx):
        """ 사용자와의 통신을 종료합니다. """
        await ctx.send(f"{ctx.author.display_name}님 안녕히계세요. 또 봬요 👋")
        await bot.close()
        # -----------------------------------
    bot.run(str(DISCORD_BOT_TOKEN))