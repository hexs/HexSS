import random
from hexss import check_packages

check_packages('shapely', auto_install=True)

from shapely.geometry import Point, LineString, Polygon, GeometryCollection
import matplotlib.pyplot as plt
import numpy as np
import cv2


def polygon_to_numpy(polygon):
    exterior_coords = np.array(polygon.exterior.coords, dtype=np.int32)
    print(exterior_coords)
    return exterior_coords.reshape((-1, 1, 2))


class Geometry:
    def __init__(self):
        self.geometries = []
        self.fig, self.ax = plt.subplots()

    def add_geometry(self, geometry, color=None):
        self.geometries.append({
            'geometry': geometry,
            'color': random.choice(['blue', 'green', 'red', 'cyan', 'magenta', 'yellow']) if color is None else color
        })

    # Function to plot a polygon
    def plot_polygon(self, polygon, color):
        exterior_coords = np.array(polygon.exterior.coords)
        self.ax.plot(exterior_coords[:, 0], exterior_coords[:, 1], color=color, linewidth=1)
        self.ax.fill(exterior_coords[:, 0], exterior_coords[:, 1], color=color, alpha=0.3)

    def show(self):
        # Plot each geometry in the collection
        for geometry in self.geometries:
            geom = geometry['geometry']
            color = geometry['color']

            if geom.geom_type == 'Point':
                self.ax.plot(geom.x, geom.y, f'{color[0]}o')
            elif geom.geom_type == 'LineString':
                self.ax.plot(*geom.xy, color=color)
            elif geom.geom_type == 'Polygon':
                self.plot_polygon(geom, color)
            elif geom.geom_type == 'GeometryCollection':
                for sub_geom in geom:
                    self.add_geometry(sub_geom, color)

        # Set plot limits and aspect ratio
        # ax.set_xlim(-2, 3)
        # ax.set_ylim(-2, 3)
        self.ax.set_aspect('equal')

        # Convert Matplotlib figure to OpenCV image
        self.fig.canvas.draw()
        img = np.array(self.fig.canvas.renderer.buffer_rgba())

        cv2.imshow('Geometry', cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA))
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    # img = np.zeros((500, 500, 3), dtype=np.uint8)
    #
    # coords = ((10, 10), (10, 40), (10, 80), (200, 400), (200, 200))
    # polygon = Polygon(coords)
    #
    # cv2.polylines(img, ([polygon_to_numpy(polygon)]), True, (255, 0, 0), 2, cv2.LINE_AA)
    # cv2.imshow('img', img)
    # cv2.waitKey(0)

    # Define points and their buffers
    point1 = Point((0, 0))
    poly1 = point1.buffer(1)
    poly2 = Point((1, 0)).buffer(1)
    line1 = LineString([(0, 0), (0, 1)])

    geo = Geometry()
    geo.add_geometry(poly1)
    geo.add_geometry(poly1.intersection(poly2), 'red')
    geo.add_geometry(point1)
    geo.add_geometry(line1)
    geo.show()
