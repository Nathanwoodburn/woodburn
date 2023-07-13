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
                    if (fileExists) {
                        mail bcc: '', body: 'Woodburn website canonical tages incorrect.', cc: '', from: 'noreply@woodburn.au', replyTo: 'noreply@woodburn.au', subject: 'Woodburn failed', to: 'jenkins@woodburn.au'
                        error("Error: Found occurrences of file names with the .html extension in the following files:\n${affectedFiles}")
                    }
                }
            }
        }
    }
}