"""16 只宝可梦的元数据表(配色 / 属性 / 性格 / 图鉴号 / 台词素材)。

【内部组装用,不是数据包本身】。配合各画师产出的 15 组帧,由组装脚本拼成最终的
pokedex/<名>.py 数据包(PACK dict)。把"非帧"的所有字段集中在这里,便于统一口径、
逐只核对配色与人设。数据来源:特征查证(PokeAPI / Bulbapedia)。
"""

# 每只一条:module(文件名)、name(中文名)、species(种族名)、dex(图鉴编号)、
# element(元素符号)、body(主体色 rgb)、cheek(脸颊点色)、element_color(元素符号色)、
# glow(兴奋光晕色)、bubble(气泡 bg/border/text)、persona_traits(性格,写人设用)、
# voice(拟声口头禅,造台词用)。
META = {
    # ── 妙蛙系(草/毒)──
    "bulbasaur": {
        "name": "妙蛙种子", "species": "种子宝可梦", "dex": 1,
        "element": "🌿", "body": (130, 190, 165), "cheek": (220, 90, 90),
        "element_color": (120, 200, 120), "glow": (150, 220, 140),
        "bubble": ("#E3F4E8", "#7FBF8C", "#234A2E"),
        "traits": "温吞憨厚、沉稳、慢热但忠诚、有点小倔强",
        "voice": "种子", "babble_word": "妙蛙",
    },
    "ivysaur": {
        "name": "妙蛙草", "species": "种子宝可梦", "dex": 2,
        "element": "🌸", "body": (108, 160, 130), "cheek": (210, 110, 150),
        "element_color": (220, 130, 160), "glow": (200, 150, 170),
        "bubble": ("#EAF1E6", "#6CA070", "#2A4A2E"),
        "traits": "认真踏实、自尊心渐强、成长期少年感",
        "voice": "妙蛙", "babble_word": "妙蛙",
    },
    "venusaur": {
        "name": "妙蛙花", "species": "种子宝可梦", "dex": 3,
        "element": "🌺", "body": (96, 150, 110), "cheek": (240, 120, 150),
        "element_color": (240, 150, 170), "glow": (220, 160, 175),
        "bubble": ("#E6EFE2", "#5E8C68", "#22401F"),
        "traits": "威严平和、大将之风、沉稳有守护感",
        "voice": "妙蛙", "babble_word": "妙蛙",
    },
    # ── 小火龙系(火 / 火飞)──
    "charmander": {
        "name": "小火龙", "species": "蜥蜴宝可梦", "dex": 4,
        "element": "🔥", "body": (244, 160, 90), "cheek": (230, 90, 70),
        "element_color": (255, 120, 40), "glow": (255, 150, 60),
        "bubble": ("#FFE8D6", "#F08A4A", "#5A2E10"),
        "traits": "活泼、热情、略娇气、忠心、有火一般的斗志",
        "voice": "火龙", "babble_word": "小火",
    },
    "charmeleon": {
        "name": "火恐龙", "species": "火焰宝可梦", "dex": 5,
        "element": "🔥", "body": (217, 100, 74), "cheek": (220, 70, 60),
        "element_color": (255, 110, 40), "glow": (255, 130, 50),
        "bubble": ("#FFE0D0", "#D9644A", "#5A2418"),
        "traits": "傲娇、桀骜、攻击性强、叛逆期少年",
        "voice": "火龙", "babble_word": "火恐",
    },
    "charizard": {
        "name": "喷火龙", "species": "火焰宝可梦", "dex": 6,
        "element": "🔥", "body": (250, 170, 109), "cheek": (235, 90, 70),
        "element_color": (242, 104, 74), "glow": (255, 140, 60),
        "bubble": ("#FFE9D2", "#FAAA6D", "#5A2A12"),
        "traits": "傲慢强大、自尊心极高、真正认主后忠诚威猛",
        "voice": "喷火", "babble_word": "喷火",
    },
    # ── 杰尼龟系(水)──
    "squirtle": {
        "name": "杰尼龟", "species": "小乌龟宝可梦", "dex": 7,
        "element": "💧", "body": (110, 180, 225), "cheek": (235, 150, 90),
        "element_color": (90, 170, 240), "glow": (130, 200, 255),
        "bubble": ("#DCEFFB", "#6FA8D6", "#1E3E5A"),
        "traits": "酷酷的、爱耍帅、有小团体领袖气质",
        "voice": "杰尼", "babble_word": "杰尼",
    },
    "wartortle": {
        "name": "卡咪龟", "species": "乌龟宝可梦", "dex": 8,
        "element": "💧", "body": (104, 148, 201), "cheek": (230, 150, 100),
        "element_color": (80, 150, 235), "glow": (120, 185, 250),
        "bubble": ("#D8E8F8", "#6894C9", "#1A3450"),
        "traits": "神秘、沉稳、内敛、老灵魂气质",
        "voice": "卡咪", "babble_word": "卡咪",
    },
    "blastoise": {
        "name": "水箭龟", "species": "甲壳宝可梦", "dex": 9,
        "element": "💧", "body": (80, 130, 195), "cheek": (225, 150, 100),
        "element_color": (70, 140, 230), "glow": (110, 175, 245),
        "bubble": ("#D2E2F4", "#5078BE", "#16304C"),
        "traits": "威严霸气、冷静、用实力说话的成熟战士",
        "voice": "水箭", "babble_word": "水箭",
    },
    # ── 呱呱泡蛙系(水 / 水恶)──
    "froakie": {
        "name": "呱呱泡蛙", "species": "泡蛙宝可梦", "dex": 656,
        "element": "💧", "body": (104, 190, 232), "cheek": (90, 130, 200),
        "element_color": (90, 180, 240), "glow": (150, 210, 250),
        "bubble": ("#DCF0FB", "#68BEE8", "#1E3E5A"),
        "traits": "表面散漫、内心机警、慵懒外表下的敏锐",
        "voice": "泡蛙", "babble_word": "呱呱",
    },
    "frogadier": {
        "name": "头领蛙", "species": "泡蛙宝可梦", "dex": 657,
        "element": "💧", "body": (50, 110, 190), "cheek": (130, 190, 230),
        "element_color": (80, 160, 235), "glow": (130, 195, 250),
        "bubble": ("#D6E6F6", "#3A6CAE", "#16304C"),
        "traits": "轻盈敏捷、开始展现忍者气质、行动迅速",
        "voice": "头领", "babble_word": "头领",
    },
    "greninja": {
        "name": "忍者蛙", "species": "忍者宝可梦", "dex": 658,
        "element": "🌀", "body": (53, 80, 152), "cheek": (231, 120, 141),
        "element_color": (120, 190, 240), "glow": (100, 160, 230),
        "bubble": ("#D4DCF0", "#354698", "#141F4A"),
        "traits": "沉默、帅气、利落、速度极快、强烈忍者美学",
        "voice": "忍", "babble_word": "忍者",
    },
    "ash_greninja": {
        "name": "小智忍者蛙", "species": "忍者宝可梦", "dex": 658,
        "element": "💫", "body": (90, 120, 200), "cheek": (200, 50, 50),
        "element_color": (180, 220, 255), "glow": (150, 200, 255),
        "bubble": ("#D6DEF4", "#3A55B0", "#16204C"),
        "traits": "羁绊深厚的极致形态、人兽合一、情绪张力极强",
        "voice": "忍", "babble_word": "忍者",
    },
    # ── 利欧路系(格斗 / 格斗钢)──
    "riolu": {
        "name": "利欧路", "species": "波导宝可梦", "dex": 447,
        "element": "✨", "body": (72, 152, 232), "cheek": (200, 60, 60),
        "element_color": (255, 235, 120), "glow": (180, 210, 255),
        "bubble": ("#DCE8FB", "#4898E8", "#1E2E5A"),
        "traits": "充沛活力、好奇心强、情绪化、内心敏感",
        "voice": "利欧", "babble_word": "利欧",
    },
    "lucario": {
        "name": "路卡利欧", "species": "波导宝可梦", "dex": 448,
        "element": "✨", "body": (74, 156, 239), "cheek": (192, 76, 75),
        "element_color": (255, 235, 120), "glow": (170, 205, 255),
        "bubble": ("#DAE6FA", "#4A9CEF", "#1A2A52"),
        "traits": "沉稳、忠诚、有正义感、骑士精神、守护者",
        "voice": "卡", "babble_word": "路卡",
    },
    "mega_lucario": {
        "name": "Mega路卡利欧", "species": "波导宝可梦", "dex": 448,
        "element": "💥", "body": (60, 170, 160), "cheek": (180, 50, 50),
        "element_color": (255, 90, 60), "glow": (255, 120, 80),
        "bubble": ("#D6EEEA", "#3CAAA0", "#143430"),
        "traits": "超进化后战斗本能主导、更野性、更具压迫感的武者",
        "voice": "卡", "babble_word": "路卡",
    },
}
