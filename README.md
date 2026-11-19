# Flask + MongoDB on Kubernetes (Minikube)

A Python Flask application connected to an authenticated MongoDB database, deployed on a local Kubernetes cluster (Minikube) with persistent storage, autoscaling, DNS-based service discovery, and resource limits.



## Application endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Returns `Welcome to the Flask app! The current time is: <Date and Time>` |
| `/data` | POST | Inserts the JSON body into MongoDB |
| `/data` | GET | Returns all stored documents (without `_id`) |

## Project structure

```
flask-mongodb-app/
├── app.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── README.md
└── k8s/
    ├── secret.yaml
    ├── mongo-pv-pvc.yaml
    ├── mongo-service.yaml
    ├── mongo-statefulset.yaml
    ├── flask-deployment.yaml
    ├── flask-service.yaml
    └── flask-hpa.yaml
```

## Prerequisites

- Python 3.8+ and pip
- Docker Desktop (running)
- Minikube
- kubectl
- A Docker Hub account (this project uses the username `atharv542`)

Commands below are for **Windows PowerShell**. Use `curl.exe` instead of `curl` in PowerShell.

---

## Part 1: Run locally 

```powershell
python3 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

docker pull mongo:latest
docker run -d -p 27017:27017 --name mongodb mongo:latest

$env:MONGODB_URI = "mongodb://localhost:27017/"
python app.py
```

The app runs at http://localhost:5000.

---

## Part 2: Build and push the Docker image

The `Dockerfile` uses `python:3.11-slim`, installs the dependencies, and starts the app with gunicorn:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
```

Build, log in, and push to Docker Hub:

```powershell
docker build -t atharv542/flask-mongo-app:1.0 .
docker login
docker push atharv542/flask-mongo-app:1.0
```



---

## Part 3: Deploy on Minikube

### 1. Start the cluster

Make sure Docker Desktop is running, then:

```powershell
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable metrics-server
kubectl get nodes
```


### 2. Apply the manifests (in order)

```powershell
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/mongo-pv-pvc.yaml
kubectl apply -f k8s/mongo-service.yaml
kubectl apply -f k8s/mongo-statefulset.yaml
kubectl apply -f k8s/flask-deployment.yaml
kubectl apply -f k8s/flask-service.yaml
kubectl apply -f k8s/flask-hpa.yaml
```

### 3. Check that everything is running

```powershell
kubectl get pods -w
kubectl get all,pv,pvc
kubectl get hpa
```


### 4. Access the app from your machine

With the Docker driver on Windows, run this in a **separate terminal and keep it open**:

```powershell
minikube service flask-service --url
```

It prints a URL such as `http://127.0.0.1:55018` (the port changes each run). Use it below.

```powershell
curl.exe http://127.0.0.1:55018/
curl.exe -X POST -H "Content-Type: application/json" -d "{\`"sampleKey\`":\`"sampleValue\`"}" http://127.0.0.1:55018/data
curl.exe http://127.0.0.1:55018/data
```

You can also open `http://127.0.0.1:55018/` and `http://127.0.0.1:55018/data` in a browser.

---

## Verification commands

**MongoDB authentication is enforced** (fails with "requires authentication"):

```powershell
kubectl exec -it mongodb-0 -- mongosh --eval "db.getSiblingDB('flask_db').data.find()"
```

**Works with credentials:**

```powershell
kubectl exec -it mongodb-0 -- mongosh -u admin -p ChangeMe123 --authenticationDatabase admin --eval "db.getSiblingDB('flask_db').data.find()"
```

**Persistence** (data survives deleting the database pod):

```powershell
kubectl delete pod mongodb-0
kubectl get pods -w
curl.exe http://127.0.0.1:55018/data
```

**Resource requests and limits:**

```powershell
kubectl describe pod mongodb-0 | findstr /i "Limits Requests cpu memory"
kubectl describe pod <flask-pod-name> | findstr /i "Limits Requests cpu memory"
```

Replace `<flask-pod-name>` with a real name from `kubectl get pods`.

---

## Kubernetes resources

| File | Resource | Purpose |
|---|---|---|
| `secret.yaml` | Secret `mongo-secret` | MongoDB root username and password |
| `mongo-pv-pvc.yaml` | PV `mongo-pv`, PVC `mongo-pvc` | 1Gi persistent storage (hostPath `/data/mongodb`) for MongoDB |
| `mongo-service.yaml` | Headless Service `mongodb-service` | Internal-only access to MongoDB |
| `mongo-statefulset.yaml` | StatefulSet `mongodb` | MongoDB with authentication enabled, mounted at `/data/db` |
| `flask-deployment.yaml` | Deployment `flask-app` | 2 Flask replicas with readiness and liveness probes |
| `flask-service.yaml` | NodePort Service `flask-service` | Exposes Flask outside the cluster (port 30080) |
| `flask-hpa.yaml` | HorizontalPodAutoscaler `flask-hpa` | Scales Flask 2 to 5 replicas at 70% CPU |

### Database authentication

The official MongoDB image reads `MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_ROOT_PASSWORD`. When they are set (here from the Secret), MongoDB creates the root user on first start and **enables authentication**. These variables only take effect when the data directory is empty.

`app.py` builds its connection string from environment variables (`MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_USERNAME`, `MONGODB_PASSWORD`). In Kubernetes the credentials are injected from the same Secret, and the connection uses `authSource=admin`. Locally, without credentials, it falls back to an unauthenticated connection.

> **Security note:** Kubernetes Secrets are only base64-encoded, not encrypted. The password in `secret.yaml` is a demo value. For real use, change it and manage secrets with a tool such as Vault or External Secrets, and do not commit real credentials to a public repository.

---

## How DNS resolution works inside the cluster

- Minikube runs **CoreDNS** as the cluster DNS server. Every pod's `/etc/resolv.conf` points to it.
- Every Service gets a DNS record in the form `<service>.<namespace>.svc.cluster.local`. Ours is `mongodb-service.default.svc.cluster.local`.
- Pods also get search domains, so inside the same namespace the short name `mongodb-service` resolves too.
- When Flask connects to `mongodb-service`, CoreDNS returns an IP. For a normal Service this is a stable ClusterIP. For our **headless** Service (`clusterIP: None`) it returns the MongoDB pod's own IP. The StatefulSet pod can also be addressed individually as `mongodb-0.mongodb-service`.
- The Flask Deployment therefore sets `MONGODB_HOST=mongodb-service`, and the connection string becomes `mongodb://admin:<password>@mongodb-service:27017/?authSource=admin`.
- IPs are never hardcoded because pod IPs change whenever a pod restarts, while the DNS name stays the same.

---

## Resource requests and limits

| Setting | Value (Flask and MongoDB) |
|---|---|
| Request | 0.2 CPU (`200m`), 250M memory |
| Limit | 0.5 CPU (`500m`), 500M memory |

- **Request** is the guaranteed minimum. The scheduler uses it to decide which node has room for the pod, and the HPA uses it as the 100% baseline when computing CPU utilisation (70% of 200m = 140m per pod).
- **Limit** is the hard maximum. A container that exceeds its CPU limit is throttled. A container that exceeds its memory limit is OOMKilled and restarted.
- Requests prevent nodes from being overcommitted and apps from being starved. Limits stop one misbehaving pod from affecting its neighbours.
- Because requests are lower than limits, the pods get the **Burstable** QoS class.
- MongoDB is started with `--wiredTigerCacheSizeGB 0.25` so its internal cache stays inside the 500M memory limit.

---


### Autoscaling

1. Open three terminals and run `kubectl get hpa flask-hpa -w` in the first and `kubectl get pods -w` in the second.
2. In the third, generate load from inside the cluster:

   ```powershell
   kubectl run load-gen-1 --rm -i --tty --image=busybox:1.36 --restart=Never -- /bin/sh -c "while true; do wget -q -O- http://flask-service:5000/data; done"
   ```

3. For heavier load, start more generators with unique names, or use a multi-loop generator:

   ```powershell
   kubectl run load-gen-2 --rm -i --tty --image=busybox:1.36 --restart=Never -- /bin/sh -c "for i in 1 2 3 4 5; do (while true; do wget -q -O- http://flask-service:5000/data > /dev/null; done) & done; wait"
   ```

4. Watch average CPU rise above the 70% target. The HPA then adds Flask replicas (up to 5).
5. Stop the load with Ctrl+C. After the stabilisation window (about 5 minutes) the HPA scales back down to the minimum of 2.

The results of these tests are demonstrated live. 
