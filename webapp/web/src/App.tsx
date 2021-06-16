import React, {useState} from 'react';
import ReactDOM from 'react-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import Savegame from './Savegame';
import Viewer from './Viewer';

function Main() {
  const [data, setData] = useState(null)

  return (
    <div>
      <Savegame setData={setData} />
      <Viewer data={data} />
    </div>
  )
}

ReactDOM.render(
  <React.StrictMode>
    <Main />
  </React.StrictMode>,
  document.getElementById('root')
);
