import libchecker

if __name__ == '__main__':
    libchecker.install_all_from_requirements_txt()

    import main
    main.main()
