import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import {decompress} from 'xz'

function Savegame(props: any) {
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const onDrop = useCallback((acceptedFiles) => {
    acceptedFiles.forEach((file: File) => {
      const reader = new FileReader()

      reader.onabort = () => console.log('file reading was aborted')
      reader.onerror = () => console.log('file reading has failed')
      reader.onload = () => {
        const buffer = reader.result
        if (buffer === null || !(buffer instanceof ArrayBuffer)) return

        setIsAnalyzing(true)
        const resultPromise = new Promise((resolve, reject) => {
          /* Small timeout for the GUI to update the "isAnalyzing" state. */
          setTimeout(() => {
            let res = decompress(new Uint8Array(buffer))
            props.setData(JSON.parse(res))
            setIsAnalyzing(false)
          }, 10);
        })
        return resultPromise
      }
      reader.readAsArrayBuffer(file)
    })

  }, [props])
  const { getRootProps, getInputProps, isDragActive } = useDropzone({onDrop})

  return (
    <div className={`card border-info container text-center mt-5 ${isDragActive ? "bg-info" : "bg-light"}`}>
      <div className="card-body" {...getRootProps()}>
        <input {...getInputProps()} />
        {
          isAnalyzing ?
            <p>Analyzing ... this might take a while ...</p> :
          isDragActive ?
            <p>Drop the savegame here ...</p> :
            <p>Drag 'n' drop your savegame here, or click to select.<br/>Savegames uploaded here never leave your computer</p>
        }
      </div>
    </div>
  )
}

export default Savegame;
