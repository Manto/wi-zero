# many code from http://d.hatena.ne.jp/yatt/20100129/1264791420

from logging import getLogger

from reversi_zero.agent.player import ReversiPlayer
from reversi_zero.config import Config, PlayWithHumanConfig
from reversi_zero.env.reversi_env import ReversiEnv, Player
from reversi_zero.lib.ggf import convert_move_to_action, convert_action_to_move
from reversi_zero.play_game.game_model import PlayWithHuman, GameEvent
from reversi_zero.lib.nonblocking_stream_reader import NonBlockingStreamReader

import re
import sys

logger = getLogger(__name__)


def start(config: Config):
    config.play_with_human.update_play_config(config.play)
    reversi_model = PlayWithHuman(config)
    CliPlayer(config, reversi_model).start()


def notify(caption, message):
    print(f"[{caption}]: {message}")


class CliPlayer(object):
    def __init__(self, config: Config, model: PlayWithHuman):
        self.model = model
        self.reader = NonBlockingStreamReader(sys.stdin)
        self.config = config
        self.player = ReversiPlayer(
            self.config, self.model, self.config.play, enable_resign=False
        )
        self.env = ReversiEnv().reset()

        self.new_game(human_is_black=True)
        self.model.add_observer(self.handle_game_event)
        self.running = False
        self.handlers = [
            # (re.compile(r"nboard ([0-9]+)"), self.nboard),
            # (re.compile(r"set depth ([0-9]+)"), self.set_depth),
            # (re.compile(r"set game (.+)"), self.set_game),
            (re.compile(r"move ([0-9]),([0-9])"), self.move),
            # (re.compile(r"hint ([0-9]+)"), self.hint),
            # (re.compile(r"go"), self.go),
            (re.compile(r"ping ([0-9]+)"), self.ping),
            # (re.compile(r"learn"), self.learn),
            # (re.compile(r"analyze"), self.analyze),
            (re.compile(r"print"), self.refresh),
            (re.compile(r"exit"), self.exit),
        ]

    def start(self):
        self.running = True
        self.reader.start(push_callback=self.push_callback)

        while self.running and not self.reader.closed:
            message = self.reader.readline(0.1)
            if message is None:
                continue
            message = message.strip()
            print(f"> {message}")
            # logger.debug(f"> {message}")
            self.handle_message(message)

    def move(self, x, y):
        x = int(x)
        y = int(y)
        if self.model.over:
            return
        # calculate coordinate from window coordinate

        if not self.model.available(x, y):
            print(f"move {x}, {y} not available!")
            return

        self.model.move(x, y)
        self.model.play_next_turn()

    # def _change_turn(self):
    #     if self.turn_of_nboard:
    #         self.turn_of_nboard = Player.black if self.turn_of_nboard == Player.white else Player.white

    def scan(self, message, regexp, func):
        match = regexp.match(message)
        if match:
            func(*match.groups())
            return True
        return False

    def handle_message(self, message):
        for regexp, func in self.handlers:
            if self.scan(message, regexp, func):
                return
        logger.debug(f"ignore message: {message}")

    def push_callback(self, message: str):
        # note: called in another thread
        print("push_callback: " + message)
        if message.startswith("ping"):  # interupt
            self.stop_thinkng()

    def stop_thinkng(self):
        print("stopping player thinking.")
        self.player.stop_thinking()

    def handle_game_event(self, event):
        if event == GameEvent.update:
            self.refresh()
        elif event == GameEvent.over:
            self.game_over()
        elif event == GameEvent.ai_move:
            self.ai_move()

    def new_game(self, human_is_black):
        self.model.start_game(human_is_black=human_is_black)
        self.model.play_next_turn()

    def ai_move(self):
        self.refresh()
        self.model.move_by_ai()
        self.model.play_next_turn()

    def game_over(self):
        # if game is over then display dialog

        black, white = self.model.number_of_black_and_white
        mes = "black: %d\nwhite: %d\n" % (black, white)
        if black == white:
            mes += "** draw **"
        else:
            mes += "winner: %s" % ["black", "white"][black < white]
        notify("game is over", mes)
        # elif self.reversi.passed != None:
        #     notify("passing turn", "pass")

    def update_status_bar(self):
        msg = (
            "current player is "
            + ["White", "Black"][self.model.next_player == Player.black]
        )
        if self.model.last_evaluation:
            msg += f"|AI Confidence={self.model.last_evaluation:.4f}"
        notify("status", msg)

    def refresh(self):
        self.update_status_bar()

        print("  ", end="")
        for y in range(8):
            print(f" {y}", end="")
        print("")

        for y in range(8):
            print(f"{y} ", end="")
            for x in range(8):
                c = self.model.stone(x, y)
                if c == Player.white:
                    print(" O", end="")
                elif c == Player.black:
                    print(" X", end="")
                else:
                    print(" _", end="")

            print("")

    # responses
    def exit(self):
        print("exit")
        exit()

    def ping(self, n):
        """Ensure synchronization when the board position is about to change.

        Required: Stop thinking and respond with "pong n".
        If the engine is analyzing a position it must stop analyzing before sending "pong n"
        otherwise NBoard will think the analysis relates to the current position.
        :param n:
        :return:
        """
        # self.engine.stop_thinkng()  # not implemented
        self.engine.reply(f"pong {n}")
