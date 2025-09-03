import pygame
import math
from Ball import Ball

class Wall:
    """Classe générique pour un mur ou une frontière."""
    def __init__(self, x, y,color):
        self.x = x
        self.y = y
        self.color = color

    def distance_to_middle(self,  ball : Ball):
        """Calculer la distance à la balle (à surcharger si nécessaire)."""
        raise NotImplementedError("Cette méthode doit être surchargée dans la sous-classe.")

    def in_the_wall(self, ball : Ball):
        """Vérifier si la balle est à l'intérieur du mur (à surcharger)."""
        raise NotImplementedError("Cette méthode doit être surchargée dans la sous-classe.")

    def area_of_wall(self):
        """Retourne l'aire (à surcharger)."""
        raise NotImplementedError("Cette méthode doit être surchargée dans la sous-classe.")

    def Correct_ball_position(self, ball : Ball):
        """Retourne l'aire (à surcharger)."""
        raise NotImplementedError("Cette méthode doit être surchargée dans la sous-classe.")

class CircleWall(Wall):
    def __init__(self, x, y, radius, start_angle, end_angle, id,color):
        self.x = x
        self.y = y
        self.radius = radius
        self.start_angle = 0
        self.end_angle = math.pi*2
        self.color = color
        self.id = id

    def draw(self, surface):
        pygame.draw.circle(surface, (0, 100, 255), (self.x, self.y), self.radius, 1)

    def distance_to_middle(self, ball : Ball):
        dx = ball.x - self.x
        dy = ball.y - self.y
        dist = math.hypot(dx, dy)
        return dist, dx, dy

    def in_the_wall(self, ball : Ball):
        dist, dx, dy = self.distance_to_middle(ball)
        return dist + ball.r < self.radius
    
    def Correct_ball_position(self, ball : Ball):
        dist, dx, dy = self.distance_to_middle(ball)
        ball.x = self.x + (dx / dist) * (self.radius - ball.r)
        ball.y = self.y + (dy / dist) * (self.radius - ball.r)

    def point_in_arc(self, ball : Ball, tol=1e-2):
        return True
    
    def area_of_wall(self):
        return math.pi * (self.radius ** 2)

class ArcWall(Wall):
    def __init__(self, x, y, radius, start_angle, end_angle, id,color):
        self.x = x
        self.y = y
        self.radius = radius
        self.start_angle = start_angle
        self.end_angle = end_angle
        self.color = color
        self.id = id

    def draw(self, surface):
        rect = pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2)
        pygame.draw.arc(surface, self.color, rect, self.start_angle, self.end_angle, 5)

    def distance_to_middle(self, ball : Ball):
        dx = ball.x - self.x
        dy = ball.y - self.y
        dist = math.hypot(dx, dy)
        angle = math.radians(math.atan2(ball.y - self.y, ball.x - self.x))
        return dist, dx, dy

    def in_the_wall(self, ball : Ball):
        dist, dx, dy = self.distance_to_middle(ball)
        return dist + ball.r < self.radius
    
    def Correct_ball_position(self, ball : Ball):
        dist, dx, dy = self.distance_to_middle(ball)
        ball.x = self.x + (dx / dist) * (self.radius - ball.r)
        ball.y = self.y + (dy / dist) * (self.radius - ball.r)

    def point_in_arc(self, ball : Ball, tol=1e-2):
        # 1. Distance au centre
        dx = ball.x - self.x
        dy = ball.y - self.y
        
        # 2. Angle du point
        angle = (2*math.pi - math.atan2(dy, dx) ) % (2*math.pi)
        angle_start = self.start_angle % (2*math.pi)
        angle_end = self.end_angle % (2*math.pi)

        # 3. Vérif si dans l'arc
        # Calcul de la différence relative modulo 2π
        diff_total = (angle_end - angle_start) % (2*math.pi)
        diff_theta = (angle - angle_start) % (2*math.pi)
        
        # theta est dans l’arc si sa position relative <= longueur de l’arc
        return diff_theta <= diff_total
    
    def area_of_wall(self):
        return math.pi * (self.radius ** 2)
