"""Custom futuristic light theme for Gradio UI."""
from gradio.themes.base import Base
from gradio.themes.utils import colors, fonts, sizes


class FuturisticTheme(Base):
    """A modern, futuristic light-themed Gradio interface."""
    
    def __init__(
        self,
        *,
        primary_hue: colors.Color = colors.blue,
        secondary_hue: colors.Color = colors.cyan,
        neutral_hue: colors.Color = colors.slate,
        spacing_size: sizes.Size = sizes.spacing_md,
        radius_size: sizes.Size = sizes.radius_md,
        text_size: sizes.Size = sizes.text_md,
        font: fonts.Font = fonts.GoogleFont("Inter"),
        font_mono: fonts.Font = fonts.GoogleFont("IBM Plex Mono"),
    ):
        super().__init__(
            primary_hue=primary_hue,
            secondary_hue=secondary_hue,
            neutral_hue=neutral_hue,
            spacing_size=spacing_size,
            radius_size=radius_size,
            text_size=text_size,
            font=font,
            font_mono=font_mono,
        )


def get_theme():
    """Get the custom futuristic theme instance."""
    return FuturisticTheme()
