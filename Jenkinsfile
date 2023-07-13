pipeline {
    agent any

    stages {
        stage('Verify canonical tags') {
            steps {
                script {
                    def fileExists = false
                    def affectedFiles = sh(
                        script: 'find . -type f -name "*.html" -exec grep -l "{}" "{}" \\;',
                        returnStdout: true
                    ).trim()
                    // If affectedFiles is not empty, set fileExists to true
                    if (affectedFiles) {
                        fileExists = true
                    }
                    // Fail the build and display the affected files
                    if (fileExists) {
                        error("Error: Found occurrences of file names with the .html extension in the following files:\n${affectedFiles}")
                    }
                }
            }
        }
    }
}