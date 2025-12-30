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
        
        # Custom color overrides for futuristic light theme
        self.set(
            # Background colors
            background_fill_primary="#F8FAFC",
            background_fill_secondary="#FFFFFF",
            
            # Primary colors
            color_accent="#3B82F6",
            color_accent_soft="#DBEAFE",
            
            # Button colors
            button_primary_background_fill="#3B82F6",
            button_primary_background_fill_hover="#2563EB",
            button_primary_text_color="#FFFFFF",
            
            button_secondary_background_fill="#E2E8F0",
            button_secondary_background_fill_hover="#CBD5E1",
            button_secondary_text_color="#334155",
            
            # Input colors
            input_background_fill="#FFFFFF",
            input_border_color="#E2E8F0",
            input_border_color_focus="#3B82F6",
            
            # Text colors
            body_text_color="#334155",
            body_text_color_subdued="#64748B",
            
            # Border colors
            border_color_primary="#E2E8F0",
            
            # Block styling
            block_background_fill="#FFFFFF",
            block_border_width="1px",
            block_shadow="0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
            
            # Progress bar
            stat_background_fill="#06B6D4",
            
            # Success/error colors
            color_green="#10B981",
            color_red="#EF4444",
            color_yellow="#F59E0B",
        )


def get_theme():
    """Get the custom futuristic theme instance."""
    return FuturisticTheme()
