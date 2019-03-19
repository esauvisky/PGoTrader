import cv2

def coordinate_picker(screencap="screencap.png"):
    # Read image
    img = cv2.imread(screencap)
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

    print(int(r[0]), int(r[1]), int(r[0] + r[2]), int(r[1] + r[3]))
    return [int(r[0]), int(r[1]), int(r[0] + r[2]), int(r[1] + r[3])]

coordinate_picker()
