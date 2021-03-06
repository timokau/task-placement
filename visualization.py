"""Some visual testing"""

import numpy as np
import matplotlib.patches as mpatches
from matplotlib import pyplot as plt
from matplotlib.widgets import Button, TextBox

from infrastructure import draw_infra
from overlay import draw_overlay
from embedding import PartialEmbedding
from draw_embedding import draw_embedding
from generator import DefaultGenerator, get_random_action


COLORS = {
    "sources_color": "red",
    "sink_color": "yellow",
    "intermediates_color": "green",
}


class Visualization:
    """Visualize embedding with its infrastructure and overlay"""

    def __init__(self, embedding: PartialEmbedding):
        self.embedding = embedding

        shape = (2, 3)
        self.infra_ax = plt.subplot2grid(shape=shape, loc=(0, 0))
        self.overlay_ax = plt.subplot2grid(shape=shape, loc=(1, 0))
        self.embedding_ax = plt.subplot2grid(
            shape=shape, loc=(0, 1), rowspan=2, colspan=2
        )
        plt.subplots_adjust(bottom=0.2)
        input_text_ax = plt.axes(
            [0.1, 0.05, 0.6, 0.075]  # left  # bottom  # width  # height
        )
        input_btn_ax = plt.axes(
            [0.7, 0.05, 0.2, 0.075]  # left  # bottom  # width  # height
        )

        self.update_infra()
        self.update_overlay()
        self.update_embedding()

        pa = mpatches.Patch
        plt.gcf().legend(
            handles=[
                pa(color=COLORS["sources_color"], label="source"),
                pa(color=COLORS["sink_color"], label="sink"),
                pa(color=COLORS["intermediates_color"], label="intermediate"),
            ]
        )

        random = get_random_action(self.embedding, rand=np.random)
        self.text_box_val = str(random)
        self.text_box = TextBox(
            input_text_ax, "Action", initial=self.text_box_val
        )

        def _update_textbox_val(new_val):
            self.text_box_val = new_val

        self.text_box.on_text_change(_update_textbox_val)

        self.submit_btn = Button(input_btn_ax, "Take action")

        def _on_clicked(_):
            self._take_action(self._parse_textbox())

        self.submit_btn.on_clicked(_on_clicked)

    def _parse_textbox(self):
        action = self.text_box_val
        possibilities = self.embedding.possibilities()
        for possibility in possibilities:
            if str(possibility) == action:
                return possibility
        return None

    def _update_textbox(self):
        next_random = get_random_action(self.embedding, rand=np.random)
        self.text_box.set_val(
            str(next_random) if next_random is not None else ""
        )

    def _take_action(self, action):
        if action is None:
            print("Action could not be parsed")
            return
        print(f"Taking action: {action}")
        success = self.embedding.take_action(*action)
        if not success:
            print("Action is not valid. The possibilities are:")
        self.update_embedding()
        self._update_textbox()
        plt.draw()

    def update_infra(self):
        """Redraws the infrastructure"""
        plt.sca(self.infra_ax)
        plt.cla()
        self.infra_ax.set_title("Infrastructure")
        draw_infra(self.embedding.infra, **COLORS)

    def update_overlay(self):
        """Redraws the overlay"""
        plt.sca(self.overlay_ax)
        plt.cla()
        self.overlay_ax.set_title("Overlay")
        draw_overlay(self.embedding.overlay, **COLORS)

    def update_embedding(self):
        """Redraws the embedding"""
        plt.sca(self.embedding_ax)
        plt.cla()
        self.embedding_ax.set_title("Embedding")
        draw_embedding(self.embedding, **COLORS)


def _main():
    embedding = DefaultGenerator().random_embedding(rand=np.random)
    Visualization(embedding)
    plt.show()


if __name__ == "__main__":
    _main()
