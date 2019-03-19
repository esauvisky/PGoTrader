import cv2
import logging

def pick_box_coordinate(image):
    # Read image
    try:
        img = cv2.imread(image)
    except TypeError:
        img = cv2.imread(image.filename)

    height, width, _ = img.shape

    # Select ROI
    cv2.namedWindow("Select", cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_EXPANDED)
    cv2.resizeWindow("Select", (int(width/2), int(height/2)))
    r = cv2.selectROI("Select", img)

    # Crop image
    imCrop = img[int(r[1]):int(r[1] + r[3]), int(r[0]):int(r[0] + r[2])]

    if imCrop.size == 0:
        return False

    # Display cropped image
    # cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
    # cv2.imshow("Image", imCrop)
    cv2.waitKey(0)

    logging.info('You picked [%s, %s, %s, %s]', int(r[0]), int(r[1]), int(r[0] + r[2]), int(r[1] + r[3]))
    return [int(r[0]), int(r[1]), int(r[0] + r[2]), int(r[1] + r[3])]
