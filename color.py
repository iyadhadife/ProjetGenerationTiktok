import colorsys
import pygame

def generate_rgb_gradient(start_rgb, end_rgb, n_steps):
    """
    Génère un dégradé de couleurs entre deux couleurs spécifiées en format RGB.

    :param start_rgb: Couleur de départ (R, G, B)
    :param end_rgb: Couleur d'arrivée (R, G, B)
    :param n_steps: Nombre de couleurs dans le dégradé
    :return: Liste de couleurs en format RGB
    """
    # Convertir les couleurs RGB en HLS
    start_hls = colorsys.rgb_to_hls(start_rgb[0] / 255.0, start_rgb[1] / 255.0, start_rgb[2] / 255.0)
    end_hls = colorsys.rgb_to_hls(end_rgb[0] / 255.0, end_rgb[1] / 255.0, end_rgb[2] / 255.0)

    # Calculer les différences entre les composantes H, L et S
    delta_h = (end_hls[0] - start_hls[0]) / (n_steps - 1)
    delta_l = (end_hls[1] - start_hls[1]) / (n_steps - 1)
    delta_s = (end_hls[2] - start_hls[2]) / (n_steps - 1)

    # Générer le dégradé
    gradient = []
    for i in range(n_steps):
        h = start_hls[0] + i * delta_h
        l = start_hls[1] + i * delta_l
        s = start_hls[2] + i * delta_s
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        gradient.append((int(r * 255), int(g * 255), int(b * 255)))

    return gradient

def create_gradient_backward_surface(width, height, color_top, color_bottom):
    """Crée une surface avec un dégradé vertical."""
    gradient_surface = pygame.Surface((width, height))
    for y in range(height):
        # Calculer la couleur interpolée pour chaque ligne
        ratio = y / height
        color = tuple(
            int(color_top[i] * (1 - ratio) + color_bottom[i] * ratio)
            for i in range(3)
        )
        pygame.draw.line(gradient_surface, color, (0, y), (width, y))
    return gradient_surface

start_color = (255, 0, 0)  # Rouge
end_color = (0, 0, 255)    # Bleu
n_colors = 10

gradient = generate_rgb_gradient(start_color, end_color, n_colors)

for color in gradient:
    print(color)