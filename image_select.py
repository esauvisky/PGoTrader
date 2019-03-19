
from tkinter import *
from tkinter.filedialog import askopenfilename

class LocationPicker(object):
    def __init__(self):
        pass

    def event2canvas(e, c): return (c.canvasx(e.x), c.canvasy(e.y))

    async def image_selector(screencap, location):
        root = Tk()

        #setting up a tkinter canvas with scrollbars
        frame = Frame(root, bd=2, relief=SUNKEN)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        xscroll = Scrollbar(frame, orient=HORIZONTAL)
        xscroll.grid(row=1, column=0, sticky=E+W)
        yscroll = Scrollbar(frame)
        yscroll.grid(row=0, column=1, sticky=N+S)
        canvas = Canvas(frame, bd=0, xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        canvas.grid(row=0, column=0, sticky=N+S+E+W)
        xscroll.config(command=canvas.xview)
        yscroll.config(command=canvas.yview)
        frame.pack(fill=BOTH, expand=1)

        #adding the image
        # File = askopenfilename(parent=root, initialdir="screencap.png",title='Choose an image.')
        # File = "/home/esauvisky/Files/Dropbox/Coding/Projects/PGoTrader/screencap.png"
        # print("opening %s" % File)
        img = PhotoImage(screencap)
        canvas.create_image(location[0], location[1], image=img, anchor="nw")
        canvas.config(scrollregion=canvas.bbox(ALL))

        #function to be called when mouse is clicked
        def printcoords(event):
            #outputting x and y coords to console
            cx, cy = event2canvas(event, canvas)
            logging("(%d, %d) / (%d, %d)" % (event.x, event.y, cx, cy))


        #mouseclick event
        canvas.bind("<ButtonPress-1>", printcoords)
        canvas.bind("<ButtonRelease-1>", printcoords)

        await root.mainloop()
