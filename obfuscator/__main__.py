import libchecker

tried_relaunch = False


def launch():
    try:
        import main
        main.main()
    except ModuleNotFoundError:
        global tried_relaunch
        if tried_relaunch:
            print("Modules are still missing after reinstall, giving up")
            exit(1)
        print("Found missing dependencies, installing...")
        libchecker.install_all_from_requirements_txt()
        print("All dependencies installed, retrying launch")
        tried_relaunch = True
        launch()


if __name__ == '__main__':
    launch()
