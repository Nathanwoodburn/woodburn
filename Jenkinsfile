pipeline {
    agent any

    stages {
        stage('Files') {
            steps {
                sh returnStdout: true, script: '''for file in *
do
    echo $file
done'''
            }
        }
    }
}