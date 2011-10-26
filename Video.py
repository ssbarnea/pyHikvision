#===============================================================================
## @package Video
#
# Provides functionality for working with video files recorded with Hikvision
#
# This module helps you open and access each frame from recorded video files.
# Once opened the video file behaves like a list (sequence) of images, you can use len(video) to get the number of frames, video[5] to get 5th frame.
#
# See also: http://www.hikvision.com/en/download.asp
#
#===============================================================================

SVN_VERSIONING = "$Id$" # Do not adjust manually!

import sys, time, logging, os, tempfile
import ctypes
from ctypes import byref

libc = ctypes.cdll.msvcrt

class Video():

    error_codes = {
        0:"No error",
        1:"Illegal input parameter",
        2:"Calling reference error (function are supposed to be called in another order).",
        3:"Set timer failure",
        4:"Video decoding failure",
        5:" Audio decoding failure",
        6:"Memory allocation failure",
        7:"File operation failure",
        8:"Create thread failure",
        9:"Create directDraw failure",
        10:"Create off-screen failure",
        11:"Buffer overflow, input stream failure",
        12:"Create sound device failure",
        13:"Set volume failure",
        14:"This API can only be called in file decoding mode",
        15:"This API can only be called in stream decoding mode",
        16:"System not support, the SDK can only work with CPU above Pentium 3",
        17:"Missing file header",
        18:"Version mismatch between encoder and decoder",
        19:"Initialize decoder failure",
        20:"File too short or unrecognizable stream",
        21:"Initialize timer failure",
        22:"BLT failure",
        23:"Update overlay surface failure",
        24:"Open video & audio stream failure",
        25:"Open video stream failure",
        26:"JPEG compression failure",
        27:"File type not supported",
        28:"Data error",
        29:"Secret key error",
        30:"Key frame decoding failure",
        }


    def __init__(self):
        self.hsdk = None
        try:
            dll = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PlayCtrl.dll")
            if not os.path.isfile(dll):
                raise Exception("File not found: %s")
            self.hsdk = ctypes.WinDLL(dll)
        except Exception, e:
            print("Unable to load HISDK player library (%s).\n%s" % (dll, e))
            raise e
        self.seconds = None
        self.frames = None
        self.width = None
        self.height = None
        self.__port = ctypes.c_uint()
        self.hsdk.PlayM4_GetPort(byref(self.__port))
        self.port = self.__port.value
        self.format = 'bmp' # 'bmp' or 'jpg'
        self.indexed = False
        if self.port != 0:
            logging.warn("Port is %s" % self.port)

    def getError(self):
        error_code = self.hsdk.PlayM4_GetLastError(self.port)
        if error_code in Video.error_codes:
            return Video.error_codes[error_code]
        else:
            return "Error [%s]" % error_code


    def open(self, filename):
        """
        @param filename string containing the filename and eventually the path to the 264 video file. The file has to be encoded using Hikvision utilities.
        """
        def cbFileRefDone(port, user_data):
            self = ctypes.cast(user_data, ctypes.py_object).value
            self.indexed = True
            print "File indexed."


        CALLBACK_FileRefDone = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32)
        if not self.hsdk.PlayM4_SetFileRefCallBack(self.port,  CALLBACK_FileRefDone(cbFileRefDone), ctypes.py_object(self)):
            logging.error("Unable to set callback for indexing")
            return False

        if not self.hsdk.PlayM4_OpenFile(self.port, filename):
            logging.error("Unable to open video file")
            return False

        time.sleep(1)
        while not self.indexed:
            print "Waiting for indexing to finish..."
            time.sleep(1)

#        if os.path.isfile(filename + "sync"):
#            logging.info("Index file detected, loading it.")
#            f = open(filename + "sync", "rb")
#            s = f.read()
#            p = ctypes.create_string_buffer(s, len(s))
#            if not self.hsdk.PlayM4_SetRefValue(self.port, byref(p), len(s)):
#                logging.error("Unable to set sync file.")

        self.seconds = self.hsdk.PlayM4_GetFileTime(self.port)
        self.frames = self.hsdk.PlayM4_GetFileTotalFrames(self.port)

        self.__width = ctypes.c_int()
        self.__height = ctypes.c_int()
        self.hsdk.PlayM4_GetPictureSize(self.port, byref(self.__width), byref(self.__height))
        self.width = self.__width.value
        self.height = self.__height.value
        self.filename = filename
        # allocate bitmap buffer
        self.nBufSize = self.width*self.height*4+4096 # x*y*4+ header size (4k should be just fine for the header)
        malloc = ctypes.cdll.msvcrt.malloc
        malloc.restype = ctypes.c_void_p

        self.pBitmap = malloc(self.nBufSize)
        #print(self.pBitmap)
        #print(self.nBufSize)

        if not self.pBitmap:
            logging.error("Failed to allocate memory.")
            return False

        self.pBmpSize = ctypes.c_int()
        self.pBmpSize.value = 0

        return self.__goToFirstFrame()

    def __goToFirstFrame(self):
        if not self.hsdk.PlayM4_Play(self.port, 0): # required, otherwise setframe will fail
            logging.error("Failed to initialize play. %s" % self.getError())
            return False

        if not self.hsdk.PlayM4_SetCurrentFrameNum(self.port, 0): # required, otherwise setframe will fail
            logging.error("Failed to set current frame num. %s" % self.getError())
            return False

            #        if not self.hsdk.PlayM4_OneByOne(self.port): # required, otherwise setframe will fail
            #            logging.error("Failed to initialize play one-by-one. %s" % self.getError())
            #            return False

        if not self.hsdk.PlayM4_Pause (self.port, 1): # also required
            logging.error("Failed to pause playback. %s" % self.getError())
            return False

        return True


    def __del__(self):
        """
        if self.pBitmap:
            ctypes.cdll.msvcrt.free(self.pBitmap)
            self.pBitmap = 0

        if self.hsdk:
            self.hsdk.PlayM4_CloseFile(self.port)

        self.hsdk.PlayM4_FreePort(self.port)
        """
        pass

    def __len__(self):
        # Returns the number of frames in the video.
        return self.frames

    def getCurrentFrameNum(self):
        x = self.hsdk.PlayM4_GetCurrentFrameNum(self.port)
        if x < 0 or x >= self.frames:
            logging.warn("PlayM4_GetCurrentFrameNum() returned %s. %s" % (x, self.getError()))
        return x

    def setCurrentFrameNum(self, frame):
        ret = video.hsdk.PlayM4_SetCurrentFrameNum (self.port, frame)
        if not ret:
            logging.error("PlayM4_SetCurrentFrameNum() returned %s. %s" % (ret, self.getError()))
        real_frame = self.getCurrentFrameNum()
        if real_frame == -1 or real_frame != frame:
            logging.error("PlayM4_SetCurrentFrameNum() failed to set the exact frame.")
            return False

        if not ret or real_frame != frame:
            # here is an ugly workaround that works, go to first frame and go onebyone until we reach the desired frame, slow but works!
            while real_frame != frame:
                #print "%s <> %s" % (real_frame, frame)
                if real_frame > frame:
                    if not self.hsdk.PlayM4_OneByOneBack(self.port):
                        logging.error("PlayM4_OneByOneBack failed. Error %s" % self.getError())
                        return False
                else:
                    if not self.hsdk.PlayM4_OneByOne(self.port):
                        logging.error("PlayM4_OneByOne failed. Error %s" % self.getError())
                        return False
                real_frame = self.getCurrentFrameNum()

            if frame != self.getCurrentFrameNum():
                logging.error("Final frame [%s] is not the expected one [%s]." % (self.getCurrentFrameNum(), frame) )
                return False

        return ret


    def __getitem__(self, key):
        if key>len(self) or key < 0:
            raise IndexError()

        if key == self.getCurrentFrameNum():
            return "x"
        else:
            res = self.hsdk.PlayM4_SetCurrentFrameNum (self.port, key)
            err = self.getError()
            res2 = self.getCurrentFrameNum()
            if not res or not res2==key:
                logging.error("Failed to set current frame. %s" % err)
                return False
            return "y" # TODO: return image

        # return wx.Bitmap(self.imageFilename, wx.BITMAP_TYPE_BMP).ConvertToImage()

    def saveFrame(self, filename = None, frame = None, delete=True):
        """
            @param filename string containing the filename to be saved. If not specified function will generate a temporary filename.
            @param delete bool telling that the filename is supposed to be deleted when the returned filehandle is closed.
        """

        if frame and not self.hsdk.PlayM4_SetCurrentFrameNum (self.port, frame):
            logging.error("Failed to set current frame")
            return False

        if self.format=='jpg':
            if not self.hsdk.PlayM4_GetJPEG(self.port, self.pBitmap, self.nBufSize, ctypes.byref(self.pBmpSize)):
                logging.error("PlayM4_GetJPEG failed. %s %s %s" % (self.nBufSize, self.pBmpSize, self.getError()))
                return False
        elif self.format=='bmp':
            if not self.hsdk.PlayM4_GetBMP(self.port, self.pBitmap, self.nBufSize, ctypes.byref(self.pBmpSize)):
                logging.error("PlayM4_GetBMP failed. %s %s %s" % (self.nBufSize, self.pBmpSize, self.getError()))
                return False
        else:
            logging.error("Format unknown.")
            return False

        if filename is None:
            suffix = ".%s" % self.format
            (os_handle, filename) = tempfile.mkstemp(suffix=suffix)
        f = open(filename,"wb")
        data = ctypes.cast(self.pBitmap, ctypes.POINTER(ctypes.c_ubyte * self.pBmpSize.value))
        byteData = ''.join(map(chr, data.contents))
        f.write(byteData)
        # we do not close the file by default because this will delete it if it was temporary
        # f.close()
        return f


    def __str__(self):
        abs_frames = self.hsdk.PlayM4_GetAbsFrameNum(self.port)
        return "Video of %s seconds, %s frames, %sx%s : %s" % (self.seconds, self.frames, self.width, self.height, self.filename)

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    video = Video()
    sample_video_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test", "sample.264")
    if not video.open(sample_video_file):
        print("Failed to open video file: [%s]" % sample_video_file)
        sys.exit(-1)

    # display information about the video
    print video

    # display number of frames in video
    #print len(video)

    #for i in video:
    #    print i
    #myfile = video.saveFrame()
    #print myfile
    #video.hsdk.PlayM4_SetCurrentFrameNum (0, 10)

    for i in range(len(video)-100, len(video)):
        sys.stdout.write("Frame: %s\n" % i)
        video.setCurrentFrameNum(i)
        real_frame = video.getCurrentFrameNum()

        if i != real_frame:
            print "Expect %s but got %s" % (i, real_frame)

