# import pygame
# pygame.init()

# W, H = 800, 500
# screen = pygame.display.set_mode((W, H))
# clock = pygame.time.Clock()

# # Surface pour la traînée (avec alpha)
# trail = pygame.Surface((W, H), pygame.SRCALPHA)

# # Balle
# x, y = W//2, H//2
# vx, vy = 5, 3
# r = 12
# ball_color = (80, 180, 255)

# running = True
# while running:
#     for event in pygame.event.get():
#         if event.type == pygame.QUIT:
#             running = False

#     # Moteur physique basique
#     x += vx
#     y += vy
#     if x - r < 0 or x + r > W: vx = -vx
#     if y - r < 0 or y + r > H: vy = -vy

#     # 1) Assombrir légèrement la surface de traînée pour faire "disparaître" l'ancien dessin
#     # Plus la valeur alpha est grande, plus la traînée s'efface vite (essayez 25, 40, etc.)
#     trail.fill((0, 0, 0, 20), special_flags=pygame.BLEND_RGBA_SUB)

#     # 2) Dessiner la balle sur la surface de traînée
#     pygame.draw.circle(trail, ball_color, (int(x), int(y)), r)

#     # 3) Dessiner le fond + la traînée + la balle "fraîche" (optionnel)
#     screen.fill((15, 15, 20))
#     screen.blit(trail, (0, 0))
#     # Dessin de la balle nette au-dessus si tu veux une tête bien visible :
#     pygame.draw.circle(screen, (255, 255, 255), (int(x), int(y)), r, 2)

#     pygame.display.flip()
#     clock.tick(60)

# pygame.quit()

