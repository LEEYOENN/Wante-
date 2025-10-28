import discord
from discord.ext import commands
from dotenv import load_dotenv
import os 

load_dotenv()

USER_ID_TO_DM = [1108003654344134686, 385313991179632641, 881770934262976572]  
 
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if __name__ == "__main__":
    intents = discord.Intents.default() # 디스코드 봇이 서버와 상호작용 할 때 어떤 종류의 이벤트를 받아올지를 설정
    client = discord.Client(intents=intents)
    is_client_ready = False
    intents.message_content = True # 메시지 내용 접근
    intents.members = True # 멤버 접근(필요 시)
    
    @client.event
    async def on_ready():
        global is_client_ready
        print(f"Tool-Bot Logged in as {client.user}")
        is_client_ready = True

        if not is_client_ready:
            return "Error: Tool-Bot is not ready."
        
        # 코드상에서 사용자에게 DM 전송하기
        # fetch_user() 를 사용하여 사용자 ID로부터 사용자 객체를 가져옵니다.
        try:
            for user in USER_ID_TO_DM:
                user = await client.fetch_user(user)

                # 사용자 객체의 send() 함수를 호출하여 DM을 보냄
                await user.send(f"안녕하세요! {user.name}님 바보! 집에가시죠 입니다.")
                print(f"성공적으로 {user.name}님에게 DM을 보냈습니다.")

            await client.close()

        except discord.NotFound:
            # 존재하지 않는 사용자 일 경우
            print(f"'{user.name}'사용자를 찾을 수 없습니다.")
        
        except discord.Forbidden:
            # 봇이 DM을 보낼 수 없는 경우 (상대방이 DM을 차단했거나, 서버 멤버가 아닐 때 등)
            print(f"'{user.name}' 해당 사용자에게 DM을 보낼 수 없습니다. (DM이 차단되었을 수 있습니다)")
        except Exception as e:
            print(f"DM 전송 중 오류 발생: {e}")

        # -----------------------------------
    client.run(str(DISCORD_BOT_TOKEN))