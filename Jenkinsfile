pipeline {
    agent any

    stages {
        stage('Test Files') {
            steps {
                // Search for occurrences of "<filename>.html"
                script {
                    def fileExists = false

                    // Find files with "<filename>.html" occurrences
                    def affectedFiles = sh returnStdout: true, script: 'grep -rl ".html" ./*.html'
                    // Trim
                    affectedFiles = affectedFiles.trim()

                    // If affectedFiles is not empty, set fileExists to true
                    if (affectedFiles) {
                        fileExists = true
                    }

                    // Fail the build and display the affected files
                    if (fileExists) {
                        error("Error: Found occurrences of 'filename.html' in the following files:\n${affectedFiles}")
                    }
                }
            }
        }
    }
}