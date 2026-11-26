# Separate computational replay. GPL-2.0-or-later; uses original GPL functions.
# Synthetic observations; no clinical or novelty adjudication.
options(warn=1, digits=14)
file_arg <- grep('^--file=', commandArgs(FALSE), value=TRUE)
stopifnot(length(file_arg)==1)
base <- dirname(normalizePath(sub('^--file=', '', file_arg)))
original <- file.path(base,'third_party','metavcov')
source(file.path(original,'r.vcov.R'))
source(file.path(original,'smd.vcov.R'))
source(file.path(original,'metafixed.R'))
out <- file.path(base,'replay-output')
dir.create(out,showWarnings=FALSE)
set.seed(409173)
B <- 300000L
rho <- -0.7
N <- rbind(c(7,12),c(9,6))
m <- c(3,2)
arm <- function(n1,n2,mm,rho,B) {
  x <- matrix(rnorm(B*n1),B,n1)
  y <- matrix(rnorm(B*n2),B,n2)
  if(mm>0) y[,seq_len(mm)] <- rho*x[,seq_len(mm)] +
    sqrt(1-rho^2)*y[,seq_len(mm)]
  cbind(rowSums((x-rowMeans(x))^2),rowSums((y-rowMeans(y))^2))
}
ss <- arm(N[1,1],N[1,2],m[1],rho,B) + arm(N[2,1],N[2,2],m[2],rho,B)
nu <- colSums(N)-2
v <- sweep(ss,2,nu,'/')
cv <- cov(v)[1,2]
influence <- (v[,1]-mean(v[,1]))*(v[,2]-mean(v[,2]))
mcse <- sd(influence)/sqrt(B)
q <- m-m/N[,1]-m/N[,2]+m^2/(N[,1]*N[,2])
kfix <- 2*sum(q)/prod(nu)
kprinted <- 2*(sum(N[,1]*N[,2]/(rowSums(N)-1))-2)/prod(nu)
overlap <- data.frame(seed=409173,repetitions=B,rho=rho,empirical=cv,mcse=mcse,
  exact=rho^2*kfix,printed=rho^2*kprinted,z=(cv-rho^2*kfix)/mcse)
stopifnot(abs(overlap$z)<3)
H1 <- diag(N[1,1])-matrix(1/N[1,1],N[1,1],N[1,1])
H2 <- diag(N[1,2])-matrix(1/N[1,2],N[1,2],N[1,2])
CC <- matrix(0,N[1,1],N[1,2])
CC[cbind(seq_len(m[1]),seq_len(m[1]))] <- 1
trace <- sum(diag(H1%*%CC%*%H2%*%t(CC)))
stopifnot(abs(trace-q[1])<1e-12)

# Keep this after the overlap simulation to preserve the independent RNG stream.
n <- 12000L
rho <- 0.8
delta <- 1.5
sigma <- matrix(c(1,rho,rho,1),2,2)
nu <- 2*n-2
W <- rWishart(B,nu,sigma)
v1 <- W[1,1,]/nu
v2 <- W[2,2,]/nu
mu <- matrix(rnorm(2*B),B,2)%*%chol(2*sigma/n)+delta
d <- cbind(mu[,1]/sqrt(v1),mu[,2]/sqrt(v2))
Jn <- 1-3/(4*nu-1)
e <- d/Jn
bn <- Jn^2*nu/(nu-2)-1
rn <- (n-1)/(2*n-1)
reported <- 4*(1-rho)/n + rn*bn*(d[,1]^2+d[,2]^2-2*rho^2*d[,1]*d[,2])
z <- (e[,1]-e[,2])/sqrt(reported)
rate <- mean(abs(z)>qnorm(.975))
vtrue <- 4*(1-rho)+delta^2*(1-rho^2)/2
vreported <- 4*(1-rho)+delta^2*(1-rho^2)/4
lim <- 2*pnorm(-qnorm(.975)*sqrt(vreported/vtrue))
wald <- data.frame(n_each=n,delta=delta,rho=rho,repetitions=B,
  rejection=rate,mcse=sqrt(rate*(1-rate)/B),limit=lim,
  empirical_nvar=n*var(e[,1]-e[,2]),mean_reported_nvar=n*mean(reported),
  true_limit=vtrue,reported_limit=vreported)
stopifnot(abs(wald$rejection-wald$limit)<3*wald$mcse)
maxerr <- c(effect=0,contrastvar=0)
for(ii in seq_len(30)) {
  fit <- smd.vcov(matrix(n,1,2),matrix(n,1,2),matrix(d[ii,],1,2),list(sigma))
  actual <- fit$list.vcov[[1]]
  maxerr[1] <- max(maxerr[1],abs(unlist(fit$ef)-e[ii,]))
  maxerr[2] <- max(maxerr[2],abs(actual[1,1]+actual[2,2]-2*actual[1,2]-reported[ii]))
}
stopifnot(all(maxerr<1e-12))

counts <- matrix(c(12,17),1,2)
cor <- matrix(c(1,-.7,-.7,1),2,2)
ov <- matrix(c(12,0,0,17),2,2)
fit <- smd.vcov(counts,counts,matrix(c(.8,-1.1),1,2),list(cor),list(ov),list(ov))
disjoint <- fit$list.vcov[[1]][1,2]
stopifnot(abs(disjoint-(-.004232723412628))<1e-14)
load(file.path(original,'Geeganage2010.rda'))
a <- Geeganage2010
stored <- cbind(a$SMD_SBP,a$SMD_DBP)
nt <- cbind(a$nt_SBP,a$nt_DBP)
nc <- cbind(a$nc_SBP,a$nc_DBP)
md <- cbind(a$MD_SBP,a$MD_DBP)
sdt <- cbind(a$sdt_SBP,a$sdt_DBP)
sdc <- cbind(a$sdc_SBP,a$sdc_DBP)
fingerprint <- md/sqrt(sdt^2+sdc^2)
stated <- md/sqrt(((nt-1)*sdt^2+(nc-1)*sdc^2)/(nt+nc-2))
stopifnot(nrow(a)==17,all(abs(stored-stated)>1e-12),max(abs(stored-fingerprint))<1e-14)
rr <- rep(list(matrix(c(1,.71,.71,1),2,2)),nrow(a))
gls <- list()
for(scenario in c('original','input_only')) {
  inp <- if(scenario=='original') stored else stated
  fit <- smd.vcov(nt,nc,inp,rr)
  pooled <- metafixed(fit$ef,fit$list.vcov)
  inv <- lapply(fit$list.vcov,solve)
  rhs <- Reduce('+',lapply(seq_len(nrow(a)),function(i) inv[[i]]%*%unlist(fit$ef[i,])))
  beta <- solve(Reduce('+',inv),rhs)
  Q <- sum(vapply(seq_len(nrow(a)),function(i) {
    residual <- unlist(fit$ef[i,])-beta
    drop(t(residual)%*%inv[[i]]%*%residual)
  },numeric(1)))
  stopifnot(max(abs(beta-pooled$coefficients))<1e-12,abs(Q-pooled$Q)<1e-10)
  gls[[scenario]] <- data.frame(scenario=scenario,SBP=beta[1],DBP=beta[2],Q=Q,
    df=pooled$df,p=pchisq(Q,pooled$df,lower.tail=FALSE))
}
write.csv(overlap,file.path(out,'independent-overlap.csv'),row.names=FALSE)
write.csv(wald,file.path(out,'independent-wald.csv'),row.names=FALSE)
write.csv(do.call(rbind,gls),file.path(out,'independent-gls.csv'),row.names=FALSE)
write.csv(data.frame(disjoint_reported=disjoint,required=0,
  fingerprint_max_abs=max(abs(stored-fingerprint)),
  stated_max_abs=max(abs(stored-stated)),trace_direct=trace,trace_scalar=q[1],
  source_effect_error=maxerr[1],source_contrast_variance_error=maxerr[2]),
  file.path(out,'independent-identities.csv'),row.names=FALSE)
print(overlap); print(wald); print(do.call(rbind,gls)); print(maxerr)
cat('Independent computational checks passed; human/source-author adjudication remains open.\n')
print(sessionInfo())
