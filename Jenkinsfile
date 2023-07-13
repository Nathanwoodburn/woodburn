pipeline {
    agent any

    stages {
        stage('Check HTML Files') {
            steps {
                // Search for occurrences of "filename.html"
                script {
                    def fileExists = false

                    // Find files with "filename.html" occurrences
                    def affectedFiles = sh(
                        script: 'find . -type f -name "*.html" -print0 | xargs -0 grep -l ".html"',
                        returnStdout: true
                    ).trim()

                    // If affectedFiles is not empty, set fileExists to true
                    if (affectedFiles) {
                        fileExists = true
                    }

                    // Fail the build and display the affected files
                    if (fileExists) {
                        error("Error: Found occurrences of '.html' in the following files:\n${affectedFiles}")
                    }
                }
            }
        }
    }
}