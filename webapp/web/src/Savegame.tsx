import React, { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import {decompress} from 'xz'

function Savegame(props: any) {
    const onDrop = useCallback((acceptedFiles) => {
    acceptedFiles.forEach((file: File) => {
      const reader = new FileReader()

      reader.onabort = () => console.log('file reading was aborted')
      reader.onerror = () => console.log('file reading has failed')
      reader.onload = () => {
        const buffer = reader.result
        if (buffer === null || !(buffer instanceof ArrayBuffer)) return

        let res = decompress(new Uint8Array(buffer))
        let data = JSON.parse(res)
        for (const chunk in data["chunks"]) {
          for (const index in data["chunks"][chunk]) {
            data["chunks"][chunk][index] = JSON.parse(data["chunks"][chunk][index])
          }
        }

        props.setData(data)
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
          isDragActive ?
            <p>Drop the savegame here ...</p> :
            <p>Drag 'n' drop your savegame here, or click to select</p>
        }
      </div>
    </div>
  )
}

export default Savegame;
