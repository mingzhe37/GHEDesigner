from ghedesigner.shape import point_polygon_check


def scale_coordinates(coordinates, scale):
    new_coordinates = []
    for x, y in coordinates:
        x *= scale
        y *= scale
        new_coordinates.append((x, y))
    return new_coordinates


def remove_cutout(coordinates, boundary, remove_inside=True, keep_contour=True):

    inside_points_idx = []
    outside_points_idx = []
    boundary_points_idx = []

    INSIDE = 1
    OUTSIDE = -1
    ON_EDGE = 0

    for idx, coordinate in enumerate(coordinates):
        coordinate = coordinates[idx]
        ret = point_polygon_check(boundary, coordinate)
        if ret == INSIDE:
            inside_points_idx.append(idx)
        elif ret == OUTSIDE:
            outside_points_idx.append(idx)
        elif ret == ON_EDGE:
            boundary_points_idx.append(idx)
        else:
            raise ValueError("Something bad happened")

    new_coordinates = []
    for idx, _ in enumerate(coordinates):
        # if we want to remove inside points and keep contour points
        if remove_inside and keep_contour:
            if idx in inside_points_idx:
                continue
            else:
                new_coordinates.append(coordinates[idx])
        # if we want to remove inside points and remove contour points
        elif remove_inside and not keep_contour:
            if idx in inside_points_idx or idx in boundary_points_idx:
                continue
            else:
                new_coordinates.append(coordinates[idx])
        # if we want to keep outside points and remove contour points
        elif not remove_inside and not keep_contour:
            if idx in outside_points_idx or idx in boundary_points_idx:
                continue
            else:
                new_coordinates.append(coordinates[idx])
        # if we want to keep outside points and keep contour points
        else:
            if idx in outside_points_idx:
                continue
            else:
                new_coordinates.append(coordinates[idx])

    return new_coordinates


def determine_largest_rectangle(property_boundary):
    x_max = 0
    y_max = 0
    for x, y in property_boundary:
        if x > x_max:
            x_max = x
        if y > y_max:
            y_max = y

    rectangle = [[0, 0], [x_max, 0], [x_max, y_max], [0, y_max], [0, 0]]

    return rectangle
