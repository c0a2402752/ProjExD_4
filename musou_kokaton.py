import math
import os
import random
import sys
import time
import pygame as pg


WIDTH = 1100  # ゲームウィンドウの幅
HEIGHT = 650  # ゲームウィンドウの高さ
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def check_bound(obj_rct: pg.Rect) -> tuple[bool, bool]:
    """
    オブジェクトが画面内or画面外を判定し，真理値タプルを返す関数
    引数：こうかとんや爆弾，ビームなどのRect
    戻り値：横方向，縦方向のはみ出し判定結果（画面内：True／画面外：False）
    """
    yoko, tate = True, True
    if obj_rct.left < 0 or WIDTH < obj_rct.right:
        yoko = False
    if obj_rct.top < 0 or HEIGHT < obj_rct.bottom:
        tate = False
    return yoko, tate


def calc_orientation(org: pg.Rect, dst: pg.Rect) -> tuple[float, float]:
    """
    orgから見て，dstがどこにあるかを計算し，方向ベクトルをタプルで返す
    引数1 org：爆弾SurfaceのRect
    引数2 dst：こうかとんSurfaceのRect
    戻り値：orgから見たdstの方向ベクトルを表すタプル
    """
    x_diff, y_diff = dst.centerx-org.centerx, dst.centery-org.centery
    norm = math.sqrt(x_diff**2+y_diff**2)
    return x_diff/norm, y_diff/norm


class Bird(pg.sprite.Sprite):
    """
    ゲームキャラクター（こうかとん）に関するクラス
    SHIFTで加速する実装を含む（元のシグネチャ num, xy を維持）
    """
    delta = {  # 押下キーと移動量の辞書（方向ベクトル）
        pg.K_UP: (0, -1),
        pg.K_DOWN: (0, +1),
        pg.K_LEFT: (-1, 0),
        pg.K_RIGHT: (+1, 0),
    }

    def __init__(self, num: int, xy: tuple[int, int], base_speed: int = 10):
        super().__init__()
        # 画像セットアップ（あなたの元の処理を踏襲）
        img0 = pg.transform.rotozoom(pg.image.load(f"fig/{num}.png"), 0, 0.9)
        img = pg.transform.flip(img0, True, False)
        self.imgs = {
            (+1, 0): img,
            (+1, -1): pg.transform.rotozoom(img, 45, 0.9),
            (0, -1): pg.transform.rotozoom(img, 90, 0.9),
            (-1, -1): pg.transform.rotozoom(img0, -45, 0.9),
            (-1, 0): img0,
            (-1, +1): pg.transform.rotozoom(img0, 45, 0.9),
            (0, +1): pg.transform.rotozoom(img, -90, 0.9),
            (+1, +1): pg.transform.rotozoom(img, -45, 0.9),
        }
        self.dire = (+1, 0)
        self.image = self.imgs[self.dire]

        # rect を xy（2要素タプル）で確実に初期化する（TypeError 回避）
        # xy が不正な場合は例外を出すよりもデフォルト位置に置く選択肢もあるが、
        # 普通は呼び出し側が正しいはずなのでそのまま使う
        self.rect = self.image.get_rect()
        self.rect.center = xy

        self.base_speed = base_speed  # 基本速度（通常は 10）
        self.speed = base_speed
        

    def change_img(self, num: int, screen: pg.Surface):
        self.image = pg.transform.rotozoom(pg.image.load(f"fig/{num}.png"), 0, 0.9)
        screen.blit(self.image, self.rect)

    def update(self, key_lst: list[bool], screen: pg.Surface):
        """
        押下キーに応じてこうかとんを移動させる。
        SHIFT（左右どちらでも）で加速する。
        """
        # SHIFT 判定（左SHIFT または 右SHIFT）
        is_shift = key_lst[pg.K_LSHIFT] or key_lst[pg.K_RSHIFT]

        # 加速倍率（必要なら調整）
        speed_mul = 1.8 if is_shift else 1.0
        cur_speed = self.base_speed * speed_mul


        sum_mv = [0, 0]
        for k, mv in __class__.delta.items():
            if key_lst[k]:
                sum_mv[0] += mv[0]
                sum_mv[1] += mv[1]

        # 移動（整数で渡すことを推奨）
        dx = int(cur_speed * sum_mv[0])
        dy = int(cur_speed * sum_mv[1])
        self.rect.move_ip(dx, dy)

        # 画面外なら移動を戻す
        if check_bound(self.rect) != (True, True):
            self.rect.move_ip(-dx, -dy)

        # 向きの更新（0,0 は無視）
        if not (sum_mv[0] == 0 and sum_mv[1] == 0):
            # 正規化された方向ベクトル（小数でよい）
            mvx, mvy = sum_mv[0], sum_mv[1]
            norm = (mvx**2 + mvy**2) ** 0.5
            if norm != 0:
                self.dire = (mvx / norm, mvy / norm)
            # 見た目の切替は元の辞書から
            # ただし sum_mv は例えば (2,0) のように合算されうるので、方向を整数に戻す
            dir_key = (int((sum_mv[0] > 0) - (sum_mv[0] < 0)),
                       int((sum_mv[1] > 0) - (sum_mv[1] < 0)))
            # dir_key が (0,0) になる可能性を回避して、既存の dire を使う
            if dir_key != (0, 0) and dir_key in self.imgs:
                self.image = self.imgs[dir_key]

        # 画面に描画
        screen.blit(self.image, self.rect)
        

class Bomb(pg.sprite.Sprite):
    """
    爆弾に関するクラス
    """
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]

    def __init__(self, emy: "Enemy", bird: Bird):
        """
        爆弾円Surfaceを生成する
        引数1 emy：爆弾を投下する敵機
        引数2 bird：攻撃対象のこうかとん
        """
        super().__init__()
        rad = random.randint(10, 50)  # 爆弾円の半径：10以上50以下の乱数
        self.image = pg.Surface((2*rad, 2*rad))
        color = random.choice(__class__.colors)  # 爆弾円の色：クラス変数からランダム選択
        pg.draw.circle(self.image, color, (rad, rad), rad)
        self.image.set_colorkey((0, 0, 0))
        self.rect = self.image.get_rect()
        # 爆弾を投下するemyから見た攻撃対象のbirdの方向を計算
        self.vx, self.vy = calc_orientation(emy.rect, bird.rect)  
        self.rect.centerx = emy.rect.centerx
        self.rect.centery = emy.rect.centery+emy.rect.height//2
        self.speed = 6

    def update(self):
        """
        爆弾を速度ベクトルself.vx, self.vyに基づき移動させる
        引数 screen：画面Surface
        """
        self.rect.move_ip(self.speed*self.vx, self.speed*self.vy)
        if check_bound(self.rect) != (True, True):
            self.kill()


class Beam(pg.sprite.Sprite):
    """
    ビームに関するクラス
    """
    def __init__(self, bird: Bird, angle0: float = 0.0):
        """
        ビーム画像Surfaceを生成する
        引数 bird：ビームを放つこうかとん
        """
        super().__init__()
        self.vx, self.vy = bird.dire
        angle = math.degrees(math.atan2(-self.vy, self.vx))
        angle = math.degrees(math.atan2(-self.vy, self.vx)) + angle0
        self.image = pg.transform.rotozoom(pg.image.load(f"fig/beam.png"), angle, 1.0)
        self.vx = math.cos(math.radians(angle))
        self.vy = -math.sin(math.radians(angle))
        self.rect = self.image.get_rect()
        self.rect.centery = bird.rect.centery+bird.rect.height*self.vy
        self.rect.centerx = bird.rect.centerx+bird.rect.width*self.vx
        self.speed = 10

    def update(self):
        """
        ビームを速度ベクトルself.vx, self.vyに基づき移動させる
        引数 screen：画面Surface
        """
        self.rect.move_ip(self.speed*self.vx, self.speed*self.vy)
        if check_bound(self.rect) != (True, True):
            self.kill()
    
def fire_spread(beams_group: pg.sprite.Group, bird: Bird, n: int = 7, spread_deg: float = 60.0): 
       if n <= 1:
           beams_group.add(Beam(bird))
           return
       start = -spread_deg / 2
       step = spread_deg / (n - 1)
       for i in range(n):
           beams_group.add(Beam(bird, angle0=start + step * i))


class Explosion(pg.sprite.Sprite):
    """
    爆発に関するクラス
    """
    def __init__(self, obj: "Bomb|Enemy", life: int):
        """
        爆弾が爆発するエフェクトを生成する
        引数1 obj：爆発するBombまたは敵機インスタンス
        引数2 life：爆発時間
        """
        super().__init__()
        img = pg.image.load(f"fig/explosion.gif")
        self.imgs = [img, pg.transform.flip(img, 1, 1)]
        self.image = self.imgs[0]
        self.rect = self.image.get_rect(center=obj.rect.center)
        self.life = life

   
    def update(self):
        """
        爆発時間を1減算した爆発経過時間_lifeに応じて爆発画像を切り替えることで
        爆発エフェクトを表現する
        """
        self.life -= 1
        self.image = self.imgs[self.life//10%2]
        if self.life < 0:
            self.kill()


class Enemy(pg.sprite.Sprite):
    """
    敵機に関するクラス
    """
    imgs = [pg.image.load(f"fig/alien{i}.png") for i in range(1, 4)]
    
    def __init__(self):
        super().__init__()
        self.image = pg.transform.rotozoom(random.choice(__class__.imgs), 0, 0.8)
        self.rect = self.image.get_rect()
        self.rect.center = random.randint(0, WIDTH), 0
        self.vx, self.vy = 0, +6
        self.bound = random.randint(50, HEIGHT//2)  # 停止位置
        self.state = "down"  # 降下状態or停止状態
        self.interval = random.randint(50, 300)  # 爆弾投下インターバル

    def update(self):
        """
        敵機を速度ベクトルself.vyに基づき移動（降下）させる
        ランダムに決めた停止位置_boundまで降下したら，_stateを停止状態に変更する
        引数 screen：画面Surface
        """
        if self.rect.centery > self.bound:
            self.vy = 0
            self.state = "stop"
        self.rect.move_ip(self.vx, self.vy)


class Score:
    """
    打ち落とした爆弾，敵機の数をスコアとして表示するクラス
    爆弾：1点
    敵機：10点
    """
    def __init__(self):
        self.font = pg.font.Font(None, 50)
        self.color = (0, 0, 255)
        self.value = 0
        self.image = self.font.render(f"Score: {self.value}", 0, self.color)
        self.rect = self.image.get_rect()
        self.rect.center = 100, HEIGHT-50

    def update(self, screen: pg.Surface):
        self.image = self.font.render(f"Score: {self.value}", 0, self.color)
        screen.blit(self.image, self.rect)


class Gravity(pg.sprite.Sprite):
    def __init__(self, life: int, screen_rect: pg.Rect):
        super().__init__()
        # 画面全体を覆う半透明Surface（SRCALPHA と RGBA）を作る
        self.image = pg.Surface((screen_rect.width, screen_rect.height), pg.SRCALPHA)
        # RGBAで黒を指定（最後の値がアルファ）
        pg.draw.rect(self.image, (0, 0, 0, 150),
                     (0, 0, screen_rect.width, screen_rect.height))
        self.rect = self.image.get_rect()
        self.life = life  # フレーム数

    def update(self, bombs: pg.sprite.Group, effects: pg.sprite.Group):
        # 発動時間を減らす
        self.life -= 1
        if self.life < 0:
            self.kill()
            return

        # 画面全体（self.rect）内の爆弾を破壊（Explosion追加 + 爆弾削除）
        # ここでは爆発の life を 40〜60 の間で固定（任意）
        to_explode = [b for b in bombs if self.rect.colliderect(b.rect)]
        for bomb in to_explode:
            effects.add(Explosion(bomb, 50))
            bomb.kill()
    

def main():
    pg.display.set_caption("真！こうかとん無双")
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    bg_img = pg.image.load(f"fig/pg_bg.jpg")
    score = Score()

    bird = Bird(3, (900, 400))
    bombs = pg.sprite.Group()
    beams = pg.sprite.Group()
    exps = pg.sprite.Group()
    emys = pg.sprite.Group()
    gravity_group = pg.sprite.Group()

    tmr = 0
    clock = pg.time.Clock()
    while True:
        key_lst = pg.key.get_pressed()
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return 0
            #if event.type == pg.KEYDOWN and event.key == pg.K_SPACE:
            #   beams.add(Beam(bird))
            if event.type == pg.KEYDOWN and event.key == pg.K_SPACE:  # Ctrl+Spaceで弾幕
                mods = pg.key.get_mods()
                if mods & pg.KMOD_CTRL:
                    fire_spread(beams, bird, n=10 , spread_deg=360.0)
                else:
                    beams.add(Beam(bird))
            if event.type == pg.KEYDOWN and event.key == pg.K_SPACE:
                beams.add(Beam(bird))
            if event.type == pg.KEYDOWN and (event.key == pg.K_RETURN or event.key == pg.K_KP_ENTER):
                # 既に重力場が無いこと、かつスコアが200以上なら発動
                if score.value >= 200 and len(gravity_group) == 0:
                    score.value -= 200
                    gravity = Gravity(400, screen.get_rect())  # 400フレーム
                    gravity_group.add(gravity)
        screen.blit(bg_img, [0, 0])

        if tmr%200== 0:  # 200フレームに1回，敵機を出現させる
            emys.add(Enemy())

        for emy in emys:
            if emy.state == "stop" and tmr%emy.interval == 0:
                # 敵機が停止状態に入ったら，intervalに応じて爆弾投下
                bombs.add(Bomb(emy, bird))

        for emy in pg.sprite.groupcollide(emys, beams, True, True).keys():  # ビームと衝突した敵機リスト
            exps.add(Explosion(emy, 100))  # 爆発エフェクト
            score.value += 10    # 10点アップ
            bird.change_img(6, screen)  # こうかとん喜びエフェクト

        for bomb in pg.sprite.groupcollide(bombs, beams, True, True).keys():  # ビームと衝突した爆弾リスト
            exps.add(Explosion(bomb, 50))  # 爆発エフェクト
            score.value += 1  # 1点アップ

        for bomb in pg.sprite.spritecollide(bird, bombs, True):  # こうかとんと衝突した爆弾リスト
            bird.change_img(8, screen)  # こうかとん悲しみエフェクト
            score.update(screen)
            pg.display.update()
            time.sleep(2)
            return

        bird.update(key_lst, screen)
        beams.update()
        beams.draw(screen)
        emys.update()
        gravity_group.update(bombs, exps)
        emys.draw(screen)
        bombs.update()
        bombs.draw(screen)
        gravity_group.draw(screen)
        exps.update()
        exps.draw(screen)
        score.update(screen)
        pg.display.update()
        tmr += 1
        clock.tick(50)


if __name__ == "__main__":
    pg.init()
    main()
    pg.quit()
    sys.exit()
