import os
import os
import uuid
import shutil
import subprocess
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI(title="Servidor de Compilación LaTeX", version="1.0.0")

class LaTeXRequest(BaseModel):
    tex_code: str
    engine: str = "pdflatex"

@app.post("/compile")
async def compile_latex(request: LaTeXRequest):
    process_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix=f"latex_compile_{process_id}_")
    
    try:
        logging.info(f"Iniciando compilación para el proceso {process_id}")
        tex_file_path = os.path.join(temp_dir, "main.tex")
        with open(tex_file_path, "w", encoding="utf-8") as f:
            f.write(request.tex_code)
        
        command = [request.engine, "-interaction=nonstopmode", "-halt-on-error", "main.tex"]
        result = subprocess.run(command, cwd=temp_dir, capture_output=True, text=True, timeout=15.0)
        pdf_file_path = os.path.join(temp_dir, "main.pdf")
        
        if result.returncode == 0 and os.path.exists(pdf_file_path):
            logging.info(f"Compilación exitosa para el proceso {process_id}")
            with open(pdf_file_path, "rb") as pdf_file:
                pdf_content = pdf_file.read()
            return Response(content=pdf_content, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename=compiled_{process_id}.pdf"})
        else:
            log_file_path = os.path.join(temp_dir, "main.log")
            error_message = "Error de compilación desconocido."
            if os.path.exists(log_file_path):
                with open(log_file_path, "r", encoding="utf-8", errors="ignore") as log_file:
                    log_content = log_file.read()
                    error_lines = [line for line in log_content.split('\n') if line.startswith('!')]
                    if error_lines:
                        error_message = "\n".join(error_lines[:10])
                    else:
                        error_message = log_content[-500:]
            logging.warning(f"Fallo en la compilación para el proceso {process_id}: {error_message}")
            raise HTTPException(status_code=400, detail=error_message)
            
    except subprocess.TimeoutExpired:
        logging.error(f"Tiempo de espera agotado para el proceso {process_id}")
        raise HTTPException(status_code=504, detail="La compilación excedió el tiempo límite de 15 segundos.")
    except HTTPException:
        raise  # Propagar errores HTTP (como el 400) sin convertirlos en 500
    except Exception as e:
        logging.error(f"Error inesperado en el servidor: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logging.info(f"Directorio temporal {temp_dir} eliminado correctamente.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
