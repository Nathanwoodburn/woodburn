pipeline {
    agent any

    stages {
        stage('Test Files') {
            steps {
                // Search for occurrences of "<filename>.html"
                script {
                    def fileError = false

                    def allFiles = sh returnStdout: true, script: 'find . -type f -name "*.html" -print0 | xargs -0 grep -l ".html"'
                    
                    // For each file, check if it contains "<filename>.html"
                    allFiles.eachLine { file ->
                        def filename = file.split("/").last()
                        def filenameWithoutExtension = filename.split("\\.").first()

                        // If the file contains "<filename>.html", set fileError to true
                        if (file.contains(filenameWithoutExtension + ".html")) {
                            fileError = true
                        }
                    }
                    // If affectedFiles is not empty, set fileExists to true
                    if (affectedFiles) {
                        fileExists = true
                    }
                    // Fail the build and display the affected files
                    if (fileError) {
                        error("Error: Found occurrences of 'filename.html' in the following files:\n${affectedFiles}")
                    }
                }
            }
        }
    }
}