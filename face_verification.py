import cv2, time
import os
import face_recognition
staticpath=r"C:\Users\Project\PycharmProjects\hand_gestured_based_ppt_controlling\images\\"

l=[]
falsecase=[]
identified = []
visit=[]
import datetime
def face_verify(img_path):
    cam = cv2.VideoCapture(0)
    currentframe = 0
    while (True):
        ret, frame = cam.read()
        try:
            print("hii")
            # if video is still left continue creating images
            name = 'a.jpg'
            print('Creating...' + name)
            import datetime
            # ddd = datetime.datetime.now().strftime("%Y-%m-%d %H%M%S")
            cv2.imwrite(staticpath + "a.jpg", frame)
            # cv2.imwrite(staticpath + ddd + ".jpg", frame)

            # writing the extracted images
            # path = "/media/" + ddd + ".jpg"
            # from PIL import Image
            # Original_Image = Image.open(staticpath + "a.jpg")
            # rotated_image2 = Original_Image.transpose(Image.ROTATE_270)
            # rotated_image2.save(staticpath + "a_270.jpg")

            print("Checking in owners list")
            known_faces = []

            try:
                pth=img_path.split("/")[-1]
                img = staticpath + pth
                print(img)
                b_img = face_recognition.load_image_file(img)
                b_imgs = face_recognition.face_encodings(b_img)[0]
                known_faces.append(b_imgs)
                print(str(len(known_faces)) + "done")
            except Exception as e:
                print("eeeeeee", e)
                pass


            unknown_image = face_recognition.load_image_file(staticpath + "a.jpg")
            unkonownpersons = face_recognition.face_encodings(unknown_image)
            if len(unkonownpersons) > 0:
                for i in range(0, len(unkonownpersons)):
                    h = unkonownpersons[i]

                    red = face_recognition.compare_faces(known_faces, h, tolerance=0.45)  # true,false,false,false]
                    print(red, " read")
                    print("Detected persons:")
                    if True in red:
                        cam.release()
                        cv2.destroyAllWindows()
                        return "Face match"
                    else:
                        cam.release()
                        cv2.destroyAllWindows()
                        return "No match"
            else:
                cam.release()
                cv2.destroyAllWindows()
                return "No face"
        except Exception as e:
            print("Loading Next frame")
            print(e)

    # Release all space and windows once done
    cam.release()
    cv2.destroyAllWindows()
    print(l)

