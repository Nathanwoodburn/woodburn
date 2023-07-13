# Get arg 1

$directory = $args[0]
if ($args.Length -eq 0) {
    Write-Host "No directory specified using current directory"
    $directory = "."
}
Write-Host "Directory: $directory"

# Go through each .html file in the directory
Get-ChildItem -Path $directory -Filter "*.html" | ForEach-Object {
    # Get the file name without extension
    $filename = $_.BaseName

    # Read the file content
    $content = Get-Content $_.FullName -Raw

    # Replace occurrences of "filename.html" with "filename" (outside HTML comments)
    $modifiedContent = $content -replace "$filename\.html", $filename

    # Save the modified content back to the file
    $modifiedContent | Set-Content $_.FullName

    Write-Host "Modified: $($_.Name)"
}