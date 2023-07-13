pipeline {
    agent any

    stages {
        stage('Files') {
            steps {
                sh returnStdout: true, script: '''for file in "$directory"/*.html; do
    if [[ -f "$file" ]]; then
        sed -i \'s/\\(<link rel="canonical" href="\\)\\(.*\\)\\(.html" \\)/\\1\\2\\3/\' "$file"
        echo "Modified: $file"
    fi
done'''
            }
        }
    }
}