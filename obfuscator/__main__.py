from libchecker import install_all_from_requirements_txt

tried_relaunch = False


def launch():
    try:
        import main
        main.main()
    except ModuleNotFoundError:
        global tried_relaunch
        if tried_relaunch:
            print("Modules are still missing after reinstall, giving up")
            print("Full error:")
            raise
        print("Found missing dependencies, installing...")
        install_all_from_requirements_txt()
        print("All dependencies installed, retrying launch")
        tried_relaunch = True
        launch()


if __name__ == '__main__':
    launch()
