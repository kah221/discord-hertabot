import discord
from discord import app_commands
from discord.ext import tasks
import os
import random
from dotenv import load_dotenv
import google.generativeai as genai
import asyncio # ランダム時間で呼び出すために必要
from ffmpeg import _ffmpeg  # 1gouのときはこっち
# from ffmpeg import FFmpeg  # 2gouのときはこっち　←同じCドラ直下に同じファイルを置いているのに何故？
from discord import ui # フォーム作成に必要
import re # splitを使うため

# .envファイルの読み込み
load_dotenv()

# Discordボットの設定
intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# geminiの設定
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

# プロンプト読み込み
with open('data.txt', encoding='utf-8') as f:
    prompt = f.read()
with open('lastword.txt', encoding='utf-8') as f:
    lastword = f.read()
prompt += lastword

# 状態変数
status = dict(
    mode_at_txt=False,
    mode_at_spk=False,
    at_txt_target=None,
    at_txt=[1, 3],
    at_spk=[1, 2],
    vc_name=None,
    vc_obj=None,
    vc_id=None,
)
print(status['at_txt'][0])

# 音声ファイルディレクトリ
sound_dir = "./mp3/"


# ------------------------------------------------------------制御変数編集
# モーダルフォーム
# フォームを作成
class EditHertaBot(ui.Modal, title='ヘルタボットの設定'):
    # 過去のステータス情報を記憶
    def __init__(self, status):
        super().__init__()
        self.old_status = status
        self.new_status = status
        print('変更前')
        print(f'self.old_status["mode_at_txt"] : {self.old_status["mode_at_txt"]}')
        print(f'self.old_status["mode_at_spk"] : {self.old_status["mode_at_spk"]}')
        print(f'self.old_status["at_txt_target"] : {self.old_status["at_txt_target"]}')
        print(f'self.old_status["at_txt"] : {self.old_status["at_txt"]}')
        print(f'self.old_status["at_spk"] : {self.old_status["at_spk"]}')
        
    
    input_mode_at_txt = ui.TextInput(label='オートメッセージモード', placeholder='空欄でoff 空欄以外でon', required=False, max_length=5, default=None)
    input_mode_at_spk = ui.TextInput(label='オートボイスモード', placeholder='空欄でoff 空欄以外でon', required=False, max_length=5, default=None)
    input_at_txt_target = ui.TextInput(label='オートメッセージの送信先TCid', placeholder='int型', required=False, max_length=30, default=None)
    input_at_txt_range = ui.TextInput(label='オートメッセージの間隔[分]', placeholder='最短 (半角スペース) 最長', required=False, max_length=5, default=None)
    input_at_spk_range = ui.TextInput(label='オートボイスの間隔[分]', placeholder='最短 (半角スペース) 最長', required=False, max_length=5, default=None)
    
    async def on_submit(self, interaction: discord.Interaction):
        form_msg = str(interaction.user.name) + ' がヘルタボットを編集\n```'
        if len(self.input_mode_at_txt.value) == 0: # 入力されなかったとき
            if self.old_status['mode_at_txt'] == True: # 過去のステータスがTrueだった時 True=>False
                form_msg += 'ｵｰﾄﾒｯｾｰｼﾞﾓｰﾄﾞ: True  --> False\n'
                self.new_status['mode_at_txt'] = False
        elif len(self.input_mode_at_txt.value) > 0: # 入力されたとき
            if self.old_status['mode_at_txt'] == False: # 過去のステータスがFalseだった時 False=>True
                form_msg += 'ｵｰﾄﾒｯｾｰｼﾞﾓｰﾄﾞ: False --> True\n'
                self.new_status['mode_at_txt'] = True
            else:
                form_msg += 'ｵｰﾄﾒｯｾｰｼﾞﾓｰﾄﾞ: True  --> True\n'

        if len(self.input_mode_at_spk.value) == 0: # 入力されなかったとき
            if self.old_status['mode_at_spk'] == True: # 過去のステータスがTrueだった時 True=>False
                form_msg += 'ｵｰﾄﾎﾞｲｽﾓｰﾄﾞ  : True  --> False\n'
                self.new_status['mode_at_spk'] = False
        elif len(self.input_mode_at_spk.value) > 0: # 入力されたとき
            if self.old_status['mode_at_spk'] == False: # 過去のステータスがFalseだった時 False=>True
                
                form_msg += 'ｵｰﾄﾎﾞｲｽﾓｰﾄﾞ  : False --> True\n'
                self.new_status['mode_at_spk'] = True

        # オートメッセージの送信先
        print(f'input_at_txt_target: {self.input_at_txt_target}')
        print(f'input_at_txt_target.value: {self.input_at_txt_target.value}')
        # print(f'type(int(input_at_txt_target)): {type(int(self.input_at_txt_target))}')
        # print(f'type(int(input_at_txt_target.value)): {type(int(self.input_at_txt_target))}')
        if len(self.input_at_txt_target.value) == 0: # 入力されなかったとき
            self.new_status['at_txt_target'] = None
        elif len(self.input_mode_at_spk.value) > 0: # 入力されたとき
            self.new_status['at_txt_target'] = int(str(self.input_at_txt_target))
            form_msg += 'ｵｰﾄﾒｯｾｰｼﾞ送信先 : ' + str(self.input_at_txt_target) + '\n'

        # オートメッセージ間隔
        if len(self.input_at_txt_range.value) > 0: # 入力されたとき
            range_list = re.split(' ', str(self.input_at_txt_range))
            range_list = [int(x) for x in range_list]
            if range_list[0] <= range_list[1]:
                self.new_status['at_txt'] = range_list
                form_msg += 'ｵｰﾄﾒｯｾｰｼﾞの間隔: ' + str(range_list[0]) + ' ~ ' + str(range_list[1]) + ' [分]\n'
            else:
                form_msg += 'ｵｰﾄﾒｯｾｰｼﾞの間隔: 値が無効  a b (a < b)'

        # オートボイス間隔
        if len(self.input_at_spk_range.value) > 0: # 入力されたとき
            range_list = re.split(' ', str(self.input_at_spk_range))
            range_list = [int(x) for x in range_list]
            if range_list[0] <= range_list[1]:
                self.new_status['at_spk'] = range_list
                form_msg += 'ｵｰﾄﾎﾞｲｽの間隔  : ' + str(range_list[0]) + ' ~ ' + str(range_list[1]) + ' [分]\n'
            else:
                form_msg += 'ｵｰﾄﾎﾞｲｽの間隔  : 値が無効  a b (a < b)'

        
        
        form_msg += '```'
        print('変更後')
        print(f'self.new_status["mode_at_txt"] : {self.new_status["mode_at_txt"]}')
        print(f'self.new_status["mode_at_spk"] : {self.new_status["mode_at_spk"]}')
        print(f'self.new_status["at_txt_target"] : {self.new_status["at_txt_target"]}')
        print(f'self.new_status["at_txt"] : {self.new_status["at_txt"]}')
        print(f'self.new_status["at_spk"] : {self.new_status["at_spk"]}')
        
        global status
        status = self.new_status
        await interaction.response.send_message(form_msg)
        return self.new_status
# フォーム呼び出し
@tree.command(name="hedit", description="ヘルタの設定")
async def hedit(interaction: discord.Interaction):
    await interaction.response.send_modal(EditHertaBot(status))
    



# ------------------------------------------------------------
# 自動（テキスト）
async def autoSpeak():
    await client.wait_until_ready()
    while not client.is_closed():
        target = client.get_channel(status['at_txt_target']) # テキストIDからチャンネルオブジェクトを取得
        if status['mode_at_txt'] == True and status['at_txt_target'] != None:
            with open('speak.txt', encoding='utf-8') as f:
                data = f.readlines()
                random_text = data[random.randint(0, len(data) - 1)]
            await target.send(random_text) # チャンネルオブジェクトからメッセージを送信するメソッドを呼び出す
            
        random_minutes = random.randint(status['at_txt'][0], status['at_txt'][1])
        await asyncio.sleep(random_minutes * 60)

# 自動（音声）
async def autoSpeakVoice():
    print(f'autoSpeakVoiceが呼び出された①')
    await client.wait_until_ready()
    print(f'autoSpeakVoiceが呼び出された②')
    while not client.is_closed():
        print(f'autoSpeakVoiceが呼び出された④')
        # 現在ヘルタがVCにいるときのみ動作
        if status['vc_obj'] != None and status['mode_at_spk'] == True:
            sound_files = [f for f in os.listdir(sound_dir) if f.endswith('mp3')] # 再生する音声ファイルを読み込む
            if not sound_files:
                print('サウンドファイルがありません')
                return
            sound_file = os.path.join(sound_dir, random.choice(sound_files)) # 抽選
            
            voice_client = client.voice_clients[0] # 現在のVCchを取得する
            voice_client.stop()
            voice_client.play(discord.FFmpegPCMAudio(sound_file), after=lambda e: print(f'Player error: {e}') if e else None)
            
        random_minutes = random.randint(status['at_spk'][0], status['at_spk'][1])
        await asyncio.sleep(random_minutes * 60)
    print(f'autoSpeakVoiceが呼び出された③')

# プレイ中のゲーム更新
async def playingGame():
    while not client.is_closed():
        lst = ['一', '二', '三', '四', '五', '六', '七', '八', '九']
        playing = '模擬宇宙「第' + str(lst[random.randint(0, 8)]) + '世界」'
        await client.change_presence(activity=discord.Game(name=playing))
        random_minutes = random.randint(3, 10)
        await asyncio.sleep(random_minutes * 60)


# ------------------------------
# DM
@client.event
async def on_message(message):
    # メッセージ送信者がBotだった場合は無視する
    if message.author.bot:
        return

    # 自分とのDM
    if str(message.channel.id) == os.getenv("HERTABOT_DM_CHID"):
        try:
            genai_res = model.generate_content(prompt + '\n次の質問に答えてください。' + message.content)
        except Exception as e:
            print(f'生成失敗： {e}')

        print(genai_res.text)
        answer = str(genai_res.text)
        
        try:
            await message.channel.send(answer)
        except Exception as e:
            print(f'Discordに送信失敗： {e}')

        with open('lastword.txt', 'w', encoding='utf-8') as f:
            f.write(answer)
        usedToken = genai_res.usage_metadata.total_token_count
        print(usedToken)
    # 他の人とのDM
    else:
        return


# ------------------------------
# 自作スラッシュコマンド
# ステータス確認
@tree.command(name="hstatus", description="ヘルタの状態")
async def hstatus(interaction: discord.Interaction):
    try:
        status_str = '```'
        status_str += 'ｵｰﾄﾒｯｾｰｼﾞﾓｰﾄﾞ: ' + str(status['mode_at_txt']) + '\n'
        status_str += 'ｵｰﾄﾎﾞｲｽﾓｰﾄﾞ  : ' + str(status['mode_at_spk']) + '\n'
        status_str += 'ｵｰﾄﾒｯｾｰｼﾞ送信先: ' + str(status['at_txt_target']) + '\n'
        status_str += '自動発言間隔: ' + str(status['at_txt'][0]) + ' ~ ' + str(status['at_txt'][1]) + ' [分]\n'
        status_str += '自動発声間隔: ' + str(status['at_spk'][0]) + ' ~ ' + str(status['at_spk'][1]) + ' [分]\n'
        status_str += 'VC名: ' + str(status['vc_name']) + '\n'
        status_str += 'VCｵﾌﾞｼﾞｪｸﾄ: ' + str(status['vc_obj']) + '\n'
        status_str += 'VCid: ' + str(status['vc_id']) + '\n'
        status_str += '```'
        # status_str += ': ' + '[min]\n'
        await interaction.response.send_message(status_str)
    except:
        await interaction.response.send_message("ヘルタはオフラインのようだ...")




# /heyherta関数
@tree.command(name="heyherta", description="ヘルタに訊く")
async def dice(interaction: discord.Interaction, message: str):
    try:
        genai_res = model.generate_content(prompt + '\n次の質問に答えてください。' + message)
    except Exception as e:
        print(f'生成失敗： {e}')

    print(genai_res.text)
    answer = str(genai_res.text)
    
    try:
        await interaction.response.send_message(f'{message}\n```{answer}```')
    except Exception as e:
        print(f'Discordに送信失敗： {e}')
    
    
    with open('lastword.txt', 'w', encoding='utf-8') as f:
        f.write(answer)
    usedToken = genai_res.usage_metadata.total_token_count
    print(usedToken)


# ボイスチャンネル入場
@tree.command(name="hvcjoin", description="ヘルタをVCに呼ぶ")
async def hvcjoin(interaction: discord.Interaction):
    # そもそもユーザがVCに参加していないとき
    if interaction.user.voice is None:
        await interaction.response.send_message("```VC参加必須```")
        return
    # ユーザがbotが参加していない別のVCにいる かつ　botはどのVCにもいない
    elif interaction.user.voice.channel != status['vc_obj'] and status['vc_obj'] == None:
        # ユーザのいるVCへ参加する
        status['vc_name'] = interaction.user.voice.channel
        status['vc_obj'] = interaction.user.voice
        status['vc_id'] = interaction.user.voice.channel.id
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("```VC参加```")
    # ユーザがbotが参加していない別のVCにいる　かつ　botはどこかのVCにいる
    elif interaction.user.voice.channel != status['vc_obj']:
        # ボットをいったん退出させる
        await interaction.guild.voice_client.disconnect()
        # ユーザのいるVCへ参加する
        status['vc_name'] = interaction.user.voice.channel
        status['vc_obj'] = interaction.user.voice
        status['vc_id'] = interaction.user.voice.channel.id
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("```VC移動```")

    else:
        # ユーザのいるVCへ参加する
        status['vc_name'] = interaction.user.voice.channel
        status['vc_obj'] = interaction.user.voice
        status['vc_id'] = interaction.user.voice.channel.id
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("```VC参加```")
    
    print(f'status["vc_name"] = {status["vc_name"]}')
    print(f'status["vc_obj"] = {status["vc_obj"]}')
    print(f'status["vc_id"] = {status["vc_id"]}')
    # target_vc_channel = interaction.user.voice.channel
    # await target_vc_channel.connect()
    # await interaction.response.send_message(f"```{target_vc_channel.name}に参加しました```")

# ボイスチャンネル退場
@tree.command(name="hvcleave", description="ヘルタがVCから退場する")
async def hvcleave(interaction: discord.Interaction):

    # そもそもボットがVCに参加していないとき
    if interaction.guild.voice_client == None:
        await interaction.response.send_message(f"```ボットはVCに参加していません```")
    else:
        status['vc_name'] = '非参加'
        status['vc_obj'] = None
        status['vc_id'] = None
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message(f"```{interaction.user.voice.channel.name}から退出しました```")


# ------------------------------
channel_sent = None
@client.event
async def on_ready():
    global channel_sent
    channel_sent = client.get_channel(1254809591573909608)
    # autoSpeak.start()
    client.loop.create_task(autoSpeak())
    client.loop.create_task(autoSpeakVoice())
    client.loop.create_task(playingGame())
    await tree.sync()
    print('起動完了')

# Discordボットを起動
client.run(os.getenv("DISCORD_TOKEN"))
