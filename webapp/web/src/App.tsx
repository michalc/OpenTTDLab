import React, {useState} from 'react';
import ReactDOM from 'react-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import Savegame from './Savegame';
import Viewer from './Viewer';

function Main() {
  const [data, setData] = useState(null)

  return (
    <div>
      <div className="card border-info bg-warning container mt-1 text-center">
        <p>Savegames have to be made with 12.0-beta1 or later</p>
      </div>

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
