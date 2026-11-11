import os

import shutil
import win32com.client
import pythoncom

def ppt_to_images(ppt_file):
    resources_folder=os.path.join(r"C:\Users\Project\PycharmProjects\hand_gestured_based_ppt_controlling", "Resources")
    if os.path.exists(resources_folder):
        print("Old files exist. Deleting old files")
        shutil.rmtree(resources_folder)
        print("Old files deleted successully")

    #   creating folder for new files
    os.makedirs("Resources", exist_ok=True)
    # Initialize COM for the current thread (must be placed before Dispatch)
    pythoncom.CoInitialize()
    #   start powerpoint
    powerpoint=win32com.client.Dispatch("PowerPoint.Application")
    # powerpoint.Visible=True


    try:
        # open presentation
        presentation=powerpoint.Presentations.Open(
            os.path.abspath(ppt_file),
            False, False, False
        )
        # export each slide
        for i, slide in enumerate(presentation.Slides, start=1):
            output_file=os.path.join(
                resources_folder, f"{i}.jpg"
            )
            slide.Export(
                output_file,
                "JPG",
                1920,
                1080
            )
            print(f"Saved : {output_file}")
        presentation.Close()
    finally:
        # powerpoint.Quit()
        print("Quitting")
    print("\nAll slides converted succesfully")